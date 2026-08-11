"""AI SQL Agent MCP Server.

Exposes a single MCP tool, `ask_database`, that lets an LLM client answer
natural-language questions about a SQLite database — safely.

Pipeline: schema introspection -> grounded SQL generation -> guardrail
validation -> read-only execution -> structured, logged response.
"""

from __future__ import annotations

import os
import sqlite3

from fastmcp import FastMCP

from .guardrails import validate_query
from .observability import trace_query
from .schema_reader import SchemaReader
from .sql_generator import SQLGenerationError, SQLGenerator, build_client_from_env

DB_PATH = os.environ.get("SQL_AGENT_DB_PATH", "example.db")
API_TOKEN = os.environ.get("SQL_AGENT_API_TOKEN")  # optional bearer-token auth
MAX_ROWS = int(os.environ.get("SQL_AGENT_MAX_ROWS", "500"))

mcp = FastMCP(name="ai-sql-agent")


def _get_connection() -> sqlite3.Connection:
    # Opened read-only at the SQLite driver level as a second layer of
    # defense beneath the guardrail SQL validation.
    uri = f"file:{DB_PATH}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _check_auth(token: str | None) -> None:
    """Simple bearer-token check. No-op if SQL_AGENT_API_TOKEN isn't set,
    so local development works without configuring auth first."""
    if API_TOKEN is None:
        return
    if token != API_TOKEN:
        raise PermissionError("Invalid or missing API token.")


@mcp.tool
def ask_database(question: str, api_token: str | None = None) -> dict:
    """Answer a natural-language question by generating and safely
    executing a read-only SQL query against the connected database.

    Args:
        question: A natural-language question about the data.
        api_token: Required if SQL_AGENT_API_TOKEN is configured on the server.

    Returns:
        A dict with either the query results or a structured error/reason.
    """
    with trace_query(question) as trace:
        try:
            _check_auth(api_token)
        except PermissionError as exc:
            trace.outcome = "rejected"
            trace.reason = str(exc)
            return {"ok": False, "error": "unauthorized", "reason": str(exc)}

        conn = _get_connection()
        try:
            schema_prompt = SchemaReader(conn).render_schema_prompt()
            generator = SQLGenerator(build_client_from_env())

            try:
                raw_sql = generator.generate(question, schema_prompt)
            except SQLGenerationError as exc:
                trace.outcome = "rejected"
                trace.reason = str(exc)
                return {"ok": False, "error": "cannot_answer", "reason": str(exc)}

            result = validate_query(raw_sql, max_rows=MAX_ROWS)
            if not result.allowed:
                trace.outcome = "rejected"
                trace.reason = result.reason
                trace.sql = raw_sql
                return {"ok": False, "error": "rejected_by_guardrails", "reason": result.reason}

            assert result.sanitized_sql is not None  # guaranteed when allowed=True
            trace.sql = result.sanitized_sql
            cursor = conn.execute(result.sanitized_sql)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

            trace.row_count = len(rows)
            trace.outcome = "success"
            return {"ok": True, "sql": result.sanitized_sql, "columns": columns, "rows": rows}
        finally:
            conn.close()


@mcp.tool
def describe_schema() -> dict:
    """Return the current database schema (tables, columns, foreign keys)."""
    conn = _get_connection()
    try:
        tables = SchemaReader(conn).read_all_tables()
        return {
            "ok": True,
            "tables": [
                {
                    "name": t.name,
                    "columns": [
                        {"name": c.name, "type": c.data_type, "primary_key": c.is_primary_key}
                        for c in t.columns
                    ],
                }
                for t in tables
            ],
        }
    finally:
        conn.close()


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run()
