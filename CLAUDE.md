# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**tl;dw** ("Too long; didn't watch") is a FastAPI web app that accepts YouTube URLs, fetches their transcripts, and summarizes them in French using a local Ollama LLM, streaming progress to the browser in real time via Server-Sent Events.

There is also a standalone shell script `tldw` at the repo root — a CLI version that calls `ollama run` and `youtube_transcript_api` directly, independent of the web app.

## Running the app

```sh
./run.sh          # creates .venv, installs deps, starts uvicorn on :8000 with --reload
```

Or manually after activating the venv:
```sh
source .venv/bin/activate
uvicorn app.main:app --reload
```

Set `OLLAMA_MODEL` to override the default (`gemma4`):
```sh
OLLAMA_MODEL=llama3 ./run.sh
```

**Prerequisite:** Ollama must be running locally with the target model pulled (`ollama pull gemma4`).

## Architecture

The request lifecycle for a summary job:

1. `POST /submit` → creates a `Video` row (status=`queued`), enqueues the DB row ID into `_queue`
2. `worker.py` — a pool of asyncio tasks drains `_queue`; `MAX_CONCURRENT=2` semaphore caps parallel LLM calls
3. `summarizer.py` — `process_video()` is an async generator that yields step events: `fetching_transcript` → `transcript_ready` → `streaming` (one chunk per LLM token) → `done` / `error`
4. `worker.py` — `_emit()` broadcasts each event to all SSE subscribers for that video ID via `_listeners` dict; events are also appended to `_progress` so late subscribers can replay them
5. Browser connects to `GET /video/{id}/stream` (SSE), listens for named events, and appends tokens to the summary box in real time

Key files:
- `app/main.py` — FastAPI routes and SSE endpoint
- `app/worker.py` — async job queue, pub/sub event fan-out
- `app/summarizer.py` — transcript fetching (`youtube-transcript-api`) + streaming LLM via `langchain-ollama`
- `app/models.py` — `Video` SQLAlchemy model (`id`, `url`, `video_id`, `status`, `summary`, `error`, `created_at`, `completed_at`)
- `app/database.py` — SQLite engine (`tldw.db`), session factory, `init_db()`
- `app/templates/index.html` — single Jinja2 template; sidebar + detail panel; SSE JS client inline

## SSE event names

The browser listens for: `processing`, `fetching_transcript`, `transcript_ready`, `streaming`, `done`, `failed`, `job_error`.

Note: `"error"` is a reserved EventSource event name (routes to `onerror`), so worker errors are emitted as `"job_error"` instead.

## Prompt

The summarization prompt is defined in `app/summarizer.py` — French, caveman style, three sentences max. Change it there to alter LLM output.
