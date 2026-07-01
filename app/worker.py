import asyncio
import logging
from datetime import UTC, datetime

from app.database import SessionLocal
from app.models import Video
from app.summarizer import process_video

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 2

# Grace period (seconds) before in-memory progress/listener state is evicted
# for a completed video. Allows late SSE subscribers to still replay events.
_EVICT_GRACE = 60.0

_queue: asyncio.Queue[int] = asyncio.Queue()
_progress: dict[int, list[dict]] = {}
_listeners: dict[int, list[asyncio.Queue[dict]]] = {}
_tasks: set[asyncio.Task[None]] = set()


def get_queue() -> asyncio.Queue[int]:
    return _queue


def subscribe(video_id: int) -> asyncio.Queue[dict]:
    q: asyncio.Queue[dict] = asyncio.Queue()
    _listeners.setdefault(video_id, []).append(q)
    # Replay already-emitted events so late subscribers catch up.
    for event in _progress.get(video_id, []):
        q.put_nowait(event)
    return q


def unsubscribe(video_id: int, q: asyncio.Queue[dict]) -> None:
    listeners = _listeners.get(video_id, [])
    if q in listeners:
        listeners.remove(q)
    if not listeners:
        _listeners.pop(video_id, None)


def _evict(video_id: int) -> None:
    """Prune in-memory state for a completed video after the grace period."""
    _progress.pop(video_id, None)
    _listeners.pop(video_id, None)


def _emit(video_id: int, event: dict) -> None:
    _progress.setdefault(video_id, []).append(event)
    for q in _listeners.get(video_id, []):
        q.put_nowait(event)
    # Schedule eviction after terminal events so the state doesn't grow forever.
    if event.get("step") in ("done", "failed"):
        try:
            asyncio.get_running_loop().call_later(_EVICT_GRACE, _evict, video_id)
        except RuntimeError:
            pass  # No running loop (e.g. in synchronous tests) — skip scheduling.


async def _handle(video_id: int) -> None:
    async with SessionLocal() as db:
        try:
            video = await db.get(Video, video_id)
            if not video:
                return

            video.status = "processing"
            await db.commit()
            _emit(video_id, {"step": "processing", "message": "Job started."})

            summary: str | None = None
            async for event in process_video(video.video_id, video.language, video.caveman):
                _emit(video_id, event)
                if event["step"] == "done":
                    summary = event["summary"]
                elif event["step"] == "error":
                    video.status = "failed"
                    video.error = event["message"]
                    await db.commit()
                    _emit(video_id, {"step": "failed", "message": event["message"]})
                    return

            video.status = "done"
            video.summary = summary
            video.completed_at = datetime.now(UTC)
            await db.commit()

        except Exception as e:
            logger.exception("Unhandled error processing video %d", video_id)
            await db.rollback()
            try:
                video = await db.get(Video, video_id)
                if video:
                    video.status = "failed"
                    video.error = str(e)
                    await db.commit()
            except Exception:
                logger.exception("Failed to persist failure status for video %d", video_id)
            _emit(video_id, {"step": "failed", "message": "An unexpected error occurred."})


async def _worker() -> None:
    while True:
        video_id = await _queue.get()
        try:
            await _handle(video_id)
        finally:
            _queue.task_done()


async def start_workers() -> None:
    for _ in range(MAX_CONCURRENT):
        task = asyncio.create_task(_worker())
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


async def stop_workers() -> None:
    for task in list(_tasks):
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
