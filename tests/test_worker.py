import asyncio

import pytest

from app.worker import _emit, _listeners, _progress, subscribe, unsubscribe


def test_subscribe_returns_queue():
    q = subscribe(1)
    assert isinstance(q, asyncio.Queue)


def test_subscribe_registers_listener():
    q = subscribe(42)
    assert q in _listeners[42]


def test_unsubscribe_removes_queue():
    q = subscribe(10)
    unsubscribe(10, q)
    assert q not in _listeners.get(10, [])


def test_unsubscribe_noop_when_not_registered():
    q = asyncio.Queue()
    unsubscribe(999, q)  # should not raise


def test_emit_appends_to_progress():
    event = {"step": "processing", "message": "started"}
    _emit(5, event)
    assert event in _progress[5]


def test_emit_notifies_listeners():
    q = subscribe(6)
    event = {"step": "done", "summary": "great vid"}
    _emit(6, event)
    assert not q.empty()
    assert q.get_nowait() == event


def test_emit_no_listeners_does_not_raise():
    _emit(7, {"step": "processing"})
    assert _progress[7][0]["step"] == "processing"


def test_subscribe_replays_past_events():
    _emit(8, {"step": "processing"})
    _emit(8, {"step": "fetching_transcript"})

    # late subscriber should get both events replayed
    q = subscribe(8)
    assert q.qsize() == 2
    assert q.get_nowait()["step"] == "processing"
    assert q.get_nowait()["step"] == "fetching_transcript"


def test_emit_multiple_listeners():
    q1 = subscribe(9)
    q2 = subscribe(9)
    event = {"step": "streaming", "chunk": "hello"}
    _emit(9, event)
    assert q1.get_nowait() == event
    assert q2.get_nowait() == event
