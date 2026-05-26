import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.auth_service import decode_token
from app.agents.orchestrator import OrchestratorAgent
from app.agents.advisor import AdvisorAgent
from app.agents.base import AgentContext

router = APIRouter()

EVENT_BUFFER_SIZE = 500
connections: dict[str, WebSocket] = {}
event_buffers: dict[str, list[dict]] = {}
event_seq: dict[str, int] = {}


@router.websocket("/ws/v1")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    user_id = None
    session_id = None

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "auth":
                try:
                    payload = decode_token(msg["token"])
                    user_id = payload["sub"]
                    session_id = msg.get("session_id", user_id)
                    connections[user_id] = ws
                    event_buffers.setdefault(session_id, [])
                    event_seq.setdefault(session_id, 0)
                    await ws.send_json({"type": "auth_ok", "session_id": session_id})
                except ValueError:
                    await ws.send_json({"type": "error", "code": "auth_failed",
                                        "message": "Invalid or expired token"})

            elif msg_type == "chat.message" and user_id:
                await _handle_chat_message(ws, user_id, session_id, msg)

            elif msg_type == "chat.cancel" and user_id:
                await ws.send_json({"type": "chat.cancelled", "session_id": session_id})

            elif msg_type == "chat.reconnect" and user_id:
                last_seq = msg.get("last_event_seq", 0)
                buffer = event_buffers.get(session_id, [])
                replay = [e for e in buffer if e.get("seq", 0) > last_seq]
                for event in replay:
                    await ws.send_json(event)
                await ws.send_json({"type": "chat.replay_done", "count": len(replay)})
                event_seq[session_id] = max(e.get("seq", 0) for e in buffer) if buffer else 0

            elif msg_type == "opportunity.action" and user_id:
                await ws.send_json({
                    "type": "opportunity.updated",
                    "opportunity_id": msg.get("opportunity_id"),
                    "status": msg.get("action"),
                })

            elif msg_type == "scan.request" and user_id:
                scan_id = msg.get("scan_id", "manual")
                await ws.send_json({
                    "type": "scan.progress", "scan_id": scan_id,
                    "status": "started", "progress_pct": 0,
                    "message": "扫描已提交，等待执行...",
                })

    except WebSocketDisconnect:
        pass
    finally:
        if user_id and user_id in connections:
            del connections[user_id]


async def _handle_chat_message(ws: WebSocket, user_id: str, session_id: str, msg: dict):
    message = msg.get("content", "")

    context = AgentContext(user_id=user_id, session_id=session_id)
    orchestrator = OrchestratorAgent()
    route = await orchestrator.run(context, {"message": message})

    advisor = AdvisorAgent()
    result = await advisor.run(context, {"message": message, "analysis": route})

    response_text = result.get("response", "")
    seq = event_seq.get(session_id, 0)

    chunk_size = 50
    for i, char_start in enumerate(range(0, len(response_text), chunk_size)):
        chunk = response_text[char_start:char_start + chunk_size]
        seq += 1
        event = {"type": "chat.chunk", "session_id": session_id,
                 "content": chunk, "seq": seq, "index": i}
        await ws.send_json(event)
        _buffer_event(session_id, event)
        await asyncio.sleep(0.02)

    seq += 1
    done_event = {"type": "chat.done", "session_id": session_id, "seq": seq}
    await ws.send_json(done_event)
    _buffer_event(session_id, done_event)
    event_seq[session_id] = seq


def _buffer_event(session_id: str, event: dict):
    buffer = event_buffers.setdefault(session_id, [])
    buffer.append(event)
    if len(buffer) > EVENT_BUFFER_SIZE:
        buffer.pop(0)


def broadcast_to_user(user_id: str, event: dict):
    if user_id in connections:
        asyncio.create_task(connections[user_id].send_json(event))
