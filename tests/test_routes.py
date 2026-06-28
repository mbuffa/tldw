from app.models import Video

# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


async def test_index_empty(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_index_lists_videos(client, db_session):
    db_session.add(Video(url="https://youtu.be/dQw4w9WgXcQ", video_id="dQw4w9WgXcQ", status="done"))
    db_session.commit()

    resp = await client.get("/")
    assert resp.status_code == 200
    assert "dQw4w9WgXcQ" in resp.text


# ---------------------------------------------------------------------------
# POST /submit
# ---------------------------------------------------------------------------


async def test_submit_valid_url_redirects(client):
    resp = await client.post(
        "/submit",
        data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "language": "French"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/video/" in resp.headers["location"]


async def test_submit_valid_url_creates_video(client, db_session):
    await client.post(
        "/submit",
        data={"url": "https://youtu.be/dQw4w9WgXcQ", "language": "English"},
        follow_redirects=False,
    )

    video = db_session.query(Video).first()
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"
    assert video.language == "English"
    assert video.status == "queued"


async def test_submit_invalid_url_returns_400(client):
    resp = await client.post("/submit", data={"url": "https://evil.com/video"})
    assert resp.status_code == 400
    assert "YouTube" in resp.text


async def test_submit_invalid_url_fetch_returns_json(client):
    resp = await client.post(
        "/submit",
        data={"url": "not-a-youtube-url"},
        headers={"x-requested-with": "fetch"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "Only YouTube URLs are allowed."


async def test_submit_fetch_header_returns_json(client):
    resp = await client.post(
        "/submit",
        data={"url": "https://youtu.be/dQw4w9WgXcQ"},
        headers={"x-requested-with": "fetch"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "dQw4w9WgXcQ"
    assert "slug" in body


async def test_submit_caveman_flag_stored(client, db_session):
    await client.post(
        "/submit",
        data={"url": "https://youtu.be/dQw4w9WgXcQ", "caveman": "true"},
        follow_redirects=False,
    )

    video = db_session.query(Video).first()
    assert video.caveman is True


# ---------------------------------------------------------------------------
# GET /video/{id}
# ---------------------------------------------------------------------------


async def test_video_page_exists(client, db_session):
    v = Video(url="https://youtu.be/dQw4w9WgXcQ", video_id="dQw4w9WgXcQ", status="done")
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)

    resp = await client.get(f"/video/{v.slug}")
    assert resp.status_code == 200
    assert "dQw4w9WgXcQ" in resp.text


async def test_video_page_not_found(client):
    resp = await client.get("/video/no-such-slug")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/videos
# ---------------------------------------------------------------------------


async def test_api_videos_empty(client):
    resp = await client.get("/api/videos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_api_videos_returns_list(client, db_session):
    db_session.add(
        Video(url="https://youtu.be/aaaaabbbbbcc", video_id="aaaaabbbbbcc", status="done")
    )
    db_session.add(
        Video(url="https://youtu.be/zzzzzyyyyyx", video_id="zzzzzyyyyyx", status="queued")
    )
    db_session.commit()

    resp = await client.get("/api/videos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = {v["video_id"] for v in data}
    assert ids == {"aaaaabbbbbcc", "zzzzzyyyyyx"}
    assert all("slug" in v for v in data)
