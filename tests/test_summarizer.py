from unittest.mock import MagicMock, patch

import pytest

from app.summarizer import (
    _is_youtube_host,
    extract_video_id,
    normalize_language,
    process_video,
)

# ---------------------------------------------------------------------------
# extract_video_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_valid(url, expected):
    assert extract_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/channel/UCxxx",
    ],
)
def test_extract_video_id_invalid(url):
    with pytest.raises(ValueError):
        extract_video_id(url)


# ---------------------------------------------------------------------------
# _is_youtube_host
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host, expected",
    [
        ("youtube.com", True),
        ("youtu.be", True),
        ("www.youtube.com", True),
        ("m.youtube.com", True),
        ("evil.youtube.com.evil.com", False),
        ("evil.com", False),
        ("", False),
    ],
)
def test_is_youtube_host(host, expected):
    assert _is_youtube_host(host) == expected


# ---------------------------------------------------------------------------
# normalize_language
# ---------------------------------------------------------------------------


def test_normalize_language_supported():
    assert normalize_language("French") == "French"
    assert normalize_language("English") == "English"


def test_normalize_language_unsupported_falls_back():
    assert normalize_language("Klingon") == "French"
    assert normalize_language("") == "French"


# ---------------------------------------------------------------------------
# process_video  (stub_llm autouse fixture provides the LLM stand-in)
# ---------------------------------------------------------------------------


def _make_transcript_mock(text: str):
    snippet = MagicMock()
    snippet.text = text
    mock_api = MagicMock()
    mock_api.return_value.fetch.return_value = [snippet]
    return mock_api


@pytest.mark.asyncio
async def test_process_video_happy_path(stub_llm):
    stub_llm.chunks = ["• Point one\n", "• Point two\n", "• Point three\n"]

    with patch("app.summarizer.YouTubeTranscriptApi", _make_transcript_mock("Hello world")):
        events = [e async for e in process_video("dQw4w9WgXcQ", "English")]

    steps = [e["step"] for e in events]
    assert steps[0] == "fetching_transcript"
    assert steps[1] == "transcript_ready"
    assert "streaming" in steps
    assert steps[-1] == "done"

    done_event = next(e for e in events if e["step"] == "done")
    assert done_event["summary"] == "".join(stub_llm.chunks)


@pytest.mark.asyncio
async def test_process_video_transcript_error():
    mock_api = MagicMock()
    mock_api.return_value.fetch.side_effect = RuntimeError("no transcript")

    with patch("app.summarizer.YouTubeTranscriptApi", mock_api):
        events = [e async for e in process_video("dQw4w9WgXcQ")]

    steps = [e["step"] for e in events]
    assert steps[0] == "fetching_transcript"
    assert steps[-1] == "error"
    assert "no transcript" in events[-1]["message"]


@pytest.mark.asyncio
async def test_process_video_llm_error(stub_llm):
    stub_llm.error = RuntimeError("ollama down")

    with patch("app.summarizer.YouTubeTranscriptApi", _make_transcript_mock("some transcript")):
        events = [e async for e in process_video("dQw4w9WgXcQ")]

    steps = [e["step"] for e in events]
    assert "error" in steps
    assert "ollama down" in next(e for e in events if e["step"] == "error")["message"]


@pytest.mark.asyncio
async def test_process_video_truncates_long_transcript():
    long_text = "word " * 50_000  # ~250 k chars > MAX_TRANSCRIPT_CHARS (200 k)

    with patch("app.summarizer.YouTubeTranscriptApi", _make_transcript_mock(long_text)):
        events = [e async for e in process_video("abc12345678")]

    ready = next(e for e in events if e["step"] == "transcript_ready")
    assert "truncated" in ready["message"]
