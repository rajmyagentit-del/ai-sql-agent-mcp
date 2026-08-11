"""Structured logging and request tracing.

Addresses baseline gap #6 (no observability). Every query attempt is logged
with a request ID, latency, outcome, and (truncated) SQL text — enough to
audit and debug in production without logging full result payloads
(which could contain sensitive data).
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger("ai_sql_agent_mcp")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s level=%(levelname)s %(message)s",
)


@dataclass
class QueryTrace:
    request_id: str
    question: str
    started_at: float = field(default_factory=time.monotonic)
    sql: str | None = None
    row_count: int | None = None
    outcome: str = "in_progress"  # in_progress | success | rejected | error
    reason: str | None = None

    def duration_ms(self) -> float:
        return (time.monotonic() - self.started_at) * 1000


@contextmanager
def trace_query(question: str):
    """Context manager that logs the full lifecycle of a query request."""
    trace = QueryTrace(request_id=str(uuid.uuid4())[:8], question=question)
    logger.info(
        "query_start request_id=%s question=%r",
        trace.request_id,
        question[:200],
    )
    try:
        yield trace
    except Exception as exc:  # noqa: BLE001 - intentionally broad: we log then re-raise
        trace.outcome = "error"
        trace.reason = str(exc)
        raise
    finally:
        logger.info(
            "query_end request_id=%s outcome=%s duration_ms=%.1f "
            "sql=%r row_count=%s reason=%r",
            trace.request_id,
            trace.outcome,
            trace.duration_ms(),
            (trace.sql or "")[:300],
            trace.row_count,
            trace.reason,
        )
