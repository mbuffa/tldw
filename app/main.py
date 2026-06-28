import asyncio
import json
import pathlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db, init_db
from app.models import Video
from app.summarizer import (
    SUPPORTED_LANGUAGES,
    extract_video_id,
    normalize_language,
)
from app.worker import get_queue, start_workers, subscribe, unsubscribe

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
    return templates.TemplateResponse(
        request, "index.html", {"videos": videos, "languages": sorted(SUPPORTED_LANGUAGES)}
    )


@app.post("/submit")
async def submit(
    request: Request,
    url: str = Form(...),
    language: str = Form("French"),
    caveman: bool = Form(False),
    db: Session = Depends(get_db),
):
    is_fetch = request.headers.get("x-requested-with") == "fetch"
    language = normalize_language(language)
    try:
        vid = extract_video_id(url)
    except ValueError:
        if is_fetch:
            return JSONResponse({"error": "Only YouTube URLs are allowed."}, status_code=400)
        videos = db.query(Video).order_by(Video.created_at.desc()).all()
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "videos": videos,
                "languages": sorted(SUPPORTED_LANGUAGES),
                "error": "Only YouTube URLs are allowed.",
                "submitted_url": url,
                "submitted_language": language,
                "submitted_caveman": caveman,
            },
            status_code=400,
        )

    video = Video(url=url, video_id=vid, status="queued", language=language, caveman=caveman)
    db.add(video)
    db.commit()
    db.refresh(video)

    await get_queue().put(video.id)
    if is_fetch:
        return JSONResponse({"slug": video.slug, "video_id": video.video_id, "url": video.url})
    return RedirectResponse(url=f"/video/{video.slug}", status_code=303)


@app.get("/video/{slug}", response_class=HTMLResponse)
async def video_page(request: Request, slug: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.slug == slug).first()
    if not video:
        raise HTTPException(status_code=404, detail="Not found")
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"videos": videos, "active_video": video, "languages": sorted(SUPPORTED_LANGUAGES)},
    )


@app.get("/video/{slug}/stream")
async def stream(slug: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.slug == slug).first()
    if not video:
        raise HTTPException(status_code=404, detail="Not found")

    vid_id = video.id
    q = subscribe(vid_id)

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                except TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue

                # "error" is a reserved EventSource name — the browser routes it
                # to onerror instead of a named listener, closing the stream silently.
                event_name = "job_error" if event["step"] == "error" else event["step"]
                yield {"event": event_name, "data": json.dumps(event)}

                if event["step"] in ("done", "failed"):
                    break
        finally:
            unsubscribe(vid_id, q)

    return EventSourceResponse(generator())


@app.get("/api/videos")
async def list_videos(db: Session = Depends(get_db)):
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return [
        {
            "slug": v.slug,
            "url": v.url,
            "video_id": v.video_id,
            "status": v.status,
            "summary": v.summary,
            "created_at": v.created_at.isoformat(),
        }
        for v in videos
    ]
