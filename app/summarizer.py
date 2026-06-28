import os
import re
from collections.abc import AsyncIterator
from urllib.parse import urlparse

from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
from youtube_transcript_api import YouTubeTranscriptApi

YOUTUBE_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})"
)

# Hosts that are considered valid YouTube origins.
_YOUTUBE_HOSTS = {"youtube.com", "youtu.be"}

SUPPORTED_LANGUAGES = {"French", "English"}
DEFAULT_LANGUAGE = "French"

CAVEMAN_CLAUSE = ", and you speak like caveman"

PROMPT = PromptTemplate.from_template(
    "Summarize (in {language}) this transcript cleanly into key takeaways, "
    "three sentences max{style}:\n\n{transcript}"
)


def normalize_language(value: str) -> str:
    """Return *value* if it is in SUPPORTED_LANGUAGES, else DEFAULT_LANGUAGE."""
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


# Practical cap — avoids sending absurdly long transcripts to the LLM
MAX_TRANSCRIPT_CHARS = 200_000


def _is_youtube_host(host: str) -> bool:
    """Return True if *host* is youtube.com, a subdomain of it, or youtu.be."""
    host = host.lower()
    return host in _YOUTUBE_HOSTS or host.endswith(".youtube.com")


def extract_video_id(url: str) -> str:
    url = url.strip().replace("\\", "")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Not a valid YouTube URL: {url}")
    if not _is_youtube_host(parsed.netloc):
        raise ValueError(f"Not a YouTube URL: {url}")
    match = YOUTUBE_ID_RE.search(url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    return match.group(1)


async def process_video(video_id: str, language: str = DEFAULT_LANGUAGE, caveman: bool = False) -> AsyncIterator[dict]:
    yield {"step": "fetching_transcript", "message": "Fetching transcript..."}

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en", "fr"])
        transcript = " ".join(snippet.text for snippet in fetched)
    except Exception as e:
        yield {"step": "error", "message": f"Failed to fetch transcript: {e}"}
        return

    truncated = len(transcript) > MAX_TRANSCRIPT_CHARS
    if truncated:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS]

    yield {
        "step": "transcript_ready",
        "message": (
            f"Transcript fetched ({len(transcript)} chars"
            f"{' — truncated to fit context' if truncated else ''}). Summarizing..."
        ),
    }

    llm = OllamaLLM(
        model=os.getenv("OLLAMA_MODEL", "gemma4"),
        temperature=0.3,
        think=False,  # suppress thinking tokens (equivalent of --hidethinking)
    )
    chain = PROMPT | llm

    summary_chunks: list[str] = []
    try:
        async for chunk in chain.astream({"transcript": transcript, "language": language, "style": CAVEMAN_CLAUSE if caveman else ""}):
            summary_chunks.append(chunk)
            yield {"step": "streaming", "chunk": chunk}
    except Exception as e:
        yield {"step": "error", "message": f"Failed to summarize: {e}"}
        return

    summary = "".join(summary_chunks)
    yield {"step": "done", "summary": summary}
