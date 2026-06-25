import asyncio
from datetime import UTC, datetime

from app.database import SessionLocal
from app.models import Video
from app.summarizer import process_video

MAX_CONCURRENT = 2

_queue: asyncio.Queue[int] = asyncio.Queue()
_progress: dict[int, list[dict]] = {}
_listeners: dict[int, list[asyncio.Queue]] = {}


def get_queue() -> asyncio.Queue:
    return _queue


def subscribe(video_id: int) -> asyncio.Queue[dict]:
    q: asyncio.Queue[dict] = asyncio.Queue()
    _listeners.setdefault(video_id, []).append(q)
    # replay already-emitted events so late subscribers catch up
    for event in _progress.get(video_id, []):
        q.put_nowait(event)
    return q


def unsubscribe(video_id: int, q: asyncio.Queue) -> None:
    listeners = _listeners.get(video_id, [])
    if q in listeners:
        listeners.remove(q)


def _emit(video_id: int, event: dict) -> None:
    _progress.setdefault(video_id, []).append(event)
    for q in _listeners.get(video_id, []):
        q.put_nowait(event)


async def _handle(video_id: int) -> None:
    db = SessionLocal()
    try:
        video = db.get(Video, video_id)
        if not video:
            return

        video.status = "processing"
        db.commit()
        _emit(video_id, {"step": "processing", "message": "Job started."})

        summary = None
        async for event in process_video(video.video_id, video.language):
            _emit(video_id, event)
            if event["step"] == "done":
                summary = event["summary"]
            elif event["step"] == "error":
                video.status = "failed"
                video.error = event["message"]
                db.commit()
                _emit(video_id, {"step": "failed", "message": event["message"]})
                return

        video.status = "done"
        video.summary = summary
        video.completed_at = datetime.now(UTC)
        db.commit()
    except Exception as e:
        db = SessionLocal()
        video = db.get(Video, video_id)
        if video:
            video.status = "failed"
            video.error = str(e)
            db.commit()
        _emit(video_id, {"step": "failed", "message": str(e)})
    finally:
        db.close()


async def _worker(sem: asyncio.Semaphore) -> None:
    while True:
        video_id = await _queue.get()
        async with sem:
            await _handle(video_id)
        _queue.task_done()


async def start_workers() -> None:
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    for _ in range(MAX_CONCURRENT + 4):  # extra workers to drain queue faster
        asyncio.create_task(_worker(sem))
