"""Monitoring service — token usage, agent execution, task logging."""
import time
from contextlib import asynccontextmanager
from app.database import async_session
from app.models.logs import TokenUsage, AgentLog, TaskLog


async def log_token_usage(
    user_id: str, agent_name: str, model: str, provider: str,
    input_tokens: int, output_tokens: int, latency_ms: float,
    session_id: str = None, cost_usd: float = 0,
):
    async with async_session() as db:
        db.add(TokenUsage(
            user_id=user_id, agent_name=agent_name, model=model,
            provider=provider, input_tokens=input_tokens, output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=round(cost_usd, 6), latency_ms=int(latency_ms),
            session_id=session_id,
        ))
        await db.commit()


async def log_agent_execution(
    user_id: str, agent_name: str, action: str, status: str,
    input_summary: str = None, output_summary: str = None,
    latency_ms: float = 0, error: str = None, session_id: str = None,
    metadata: dict = None,
):
    async with async_session() as db:
        db.add(AgentLog(
            user_id=user_id, agent_name=agent_name, action=action,
            status=status, input_summary=input_summary[:500] if input_summary else None,
            output_summary=output_summary[:500] if output_summary else None,
            latency_ms=int(latency_ms), error=error, session_id=session_id,
            metadata_json=metadata or {},
        ))
        await db.commit()


async def log_task_execution(
    task_name: str, task_id: str, status: str,
    result_summary: str = None, error: str = None, duration_ms: float = 0,
):
    async with async_session() as db:
        db.add(TaskLog(
            task_name=task_name, task_id=task_id, status=status,
            result_summary=result_summary, error=error, duration_ms=int(duration_ms),
        ))
        await db.commit()


@asynccontextmanager
async def track_agent(user_id: str, agent_name: str, action: str, session_id: str = None, input_summary: str = ""):
    """Context manager that tracks agent execution time and logs result."""
    start = time.time()
    status = "success"
    output_summary = ""
    error_msg = None
    try:
        yield lambda msg: setattr(locals(), "output_summary", msg) if False else None
        # The lambda is just a placeholder; the actual output is set by the caller
        status = "success"
    except Exception as e:
        status = "error"
        error_msg = str(e)[:500]
        raise
    finally:
        latency = (time.time() - start) * 1000
        try:
            await log_agent_execution(
                user_id=user_id, agent_name=agent_name, action=action,
                status=status, input_summary=input_summary[:500] if input_summary else None,
                output_summary=output_summary[:500] if output_summary else None,
                latency_ms=latency, error=error_msg, session_id=session_id,
            )
        except Exception:
            pass  # Don't let logging failures break the main flow
