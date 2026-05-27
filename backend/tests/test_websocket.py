import pytest
from unittest.mock import AsyncMock, MagicMock
from app.api.websocket import _buffer_event, event_buffers, event_seq


def test_buffer_event_stores_event():
    session_id = "test-session"
    event_buffers[session_id] = []
    _buffer_event(session_id, {"type": "chat.chunk", "seq": 1, "content": "hello"})
    assert len(event_buffers[session_id]) == 1
    assert event_buffers[session_id][0]["type"] == "chat.chunk"
    del event_buffers[session_id]


def test_buffer_event_limits_buffer_size():
    session_id = "test-session-limits"
    event_buffers[session_id] = []
    for i in range(600):
        _buffer_event(session_id, {"type": "chat.chunk", "seq": i, "content": f"msg{i}"})
    assert len(event_buffers[session_id]) <= 500
    assert event_buffers[session_id][0]["seq"] == 100
    del event_buffers[session_id]


def test_buffer_event_preserves_order():
    session_id = "test-session-order"
    event_buffers[session_id] = []
    _buffer_event(session_id, {"seq": 1})
    _buffer_event(session_id, {"seq": 2})
    _buffer_event(session_id, {"seq": 3})
    assert [e["seq"] for e in event_buffers[session_id]] == [1, 2, 3]
    del event_buffers[session_id]


def test_buffer_event_handles_missing_seq():
    session_id = "test-session-noseq"
    event_buffers[session_id] = []
    _buffer_event(session_id, {"type": "error", "message": "bad"})
    assert len(event_buffers[session_id]) == 1
    del event_buffers[session_id]
