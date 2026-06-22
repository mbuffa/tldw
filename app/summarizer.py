import os
import re
from typing import AsyncIterator
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate


YOUTUBE_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})"
)

PROMPT = PromptTemplate.from_template(
    "Summarize (in French) this transcript cleanly into key takeaways, "
    "three sentences max, and you speak like caveman:\n\n{transcript}"
)


def extract_video_id(url: str) -> str:
    match = YOUTUBE_ID_RE.search(url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    return match.group(1)


async def process_video(video_id: str) -> AsyncIterator[dict]:
    yield {"step": "fetching_transcript", "message": "Fetching transcript..."}

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en", "fr"])
        transcript = " ".join(snippet.text for snippet in fetched)
    except Exception as e:
        yield {"step": "error", "message": f"Failed to fetch transcript: {e}"}
        return

    yield {
        "step": "transcript_ready",
        "message": f"Transcript fetched ({len(transcript)} chars). Summarizing...",
    }

    llm = OllamaLLM(
        model=os.getenv("OLLAMA_MODEL", "gemma4"),
        temperature=0.3,
        reasoning=False,  # suppress thinking tokens (equivalent of --hidethinking)
        num_ctx=8192,     # long transcripts need headroom
    )
    chain = PROMPT | llm

    summary_chunks: list[str] = []
    try:
        async for chunk in chain.astream({"transcript": transcript}):
            summary_chunks.append(chunk)
            yield {"step": "streaming", "chunk": chunk}
    except Exception as e:
        yield {"step": "error", "message": f"Failed to summarize: {e}"}
        return

    summary = "".join(summary_chunks)
    yield {"step": "done", "summary": summary}
