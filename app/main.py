import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.database import get_db, init_db
from app.models import Video
from app.summarizer import extract_video_id
from app.worker import get_queue, subscribe, unsubscribe, start_workers

import json
import pathlib

templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await start_workers()
    yield


app = FastAPI(title="tl;dw", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return templates.TemplateResponse(request, "index.html", {"videos": videos})


@app.post("/submit")
async def submit(request: Request, url: str = Form(...), db: Session = Depends(get_db)):
    try:
        vid = extract_video_id(url)
    except ValueError:
        videos = db.query(Video).order_by(Video.created_at.desc()).all()
        return templates.TemplateResponse(
            request,
            "index.html",
            {"videos": videos, "error": "Only YouTube URLs are allowed.", "submitted_url": url},
            status_code=400,
        )

    video = Video(url=url, video_id=vid, status="queued")
    db.add(video)
    db.commit()
    db.refresh(video)

    await get_queue().put(video.id)
    return RedirectResponse(url=f"/video/{video.id}", status_code=303)


@app.get("/video/{video_id}", response_class=HTMLResponse)
async def video_page(request: Request, video_id: int, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Not found")
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return templates.TemplateResponse(
        request, "index.html", {"videos": videos, "active_video": video}
    )


@app.get("/video/{video_id}/stream")
async def stream(video_id: int, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Not found")

    q = subscribe(video_id)

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue

                # "error" is a reserved EventSource name — the browser routes it
                # to onerror instead of a named listener, closing the stream silently.
                event_name = "job_error" if event["step"] == "error" else event["step"]
                yield {"event": event_name, "data": json.dumps(event)}

                if event["step"] in ("done", "failed"):
                    break
        finally:
            unsubscribe(video_id, q)

    return EventSourceResponse(generator())


@app.get("/api/videos")
async def list_videos(db: Session = Depends(get_db)):
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return [
        {
            "id": v.id,
            "url": v.url,
            "video_id": v.video_id,
            "status": v.status,
            "summary": v.summary,
            "created_at": v.created_at.isoformat(),
        }
        for v in videos
    ]
