"""Query safety guardrails.

This is the module that makes this project meaningfully different from a
typical "LLM writes SQL, we run it" demo. It addresses baseline gaps #1, #2,
and #4 (no query safety layer, no read-only enforcement, no result-size caps).

Design principle: never trust generated SQL. Validate it structurally before
it ever touches the database connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Statement types that are never allowed, regardless of DB permissions.
# Defense in depth: even if the DB connection somehow had write access,
# we refuse to forward these statement types.
_FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
)

_MAX_ROW_LIMIT_DEFAULT = 500


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    sanitized_sql: str | None = None


def _strip_sql_comments(sql: str) -> str:
    """Remove -- and /* */ comments so keyword checks can't be evaded."""
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def validate_query(sql: str, max_rows: int = _MAX_ROW_LIMIT_DEFAULT) -> GuardrailResult:
    """Validate a generated SQL statement before execution.

    Enforces:
      1. Single statement only (blocks statement-stacking via ';').
      2. Must start with SELECT (read-only enforcement).
      3. No forbidden keywords anywhere in the statement.
      4. Injects a LIMIT clause if the query doesn't already have one,
         capped at max_rows, to prevent unbounded result sets.
    """
    if not sql or not sql.strip():
        return GuardrailResult(allowed=False, reason="Empty query.")

    cleaned = _strip_sql_comments(sql).strip()

    # Block multiple statements (e.g. "SELECT ...; DROP TABLE ...")
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) != 1:
        return GuardrailResult(
            allowed=False,
            reason="Only a single SQL statement is permitted per request.",
        )

    single_statement = statements[0]
    upper = single_statement.upper()

    if not upper.startswith("SELECT") and not upper.startswith("WITH"):
        return GuardrailResult(
            allowed=False,
            reason="Only read-only SELECT queries are permitted.",
        )

    for keyword in _FORBIDDEN_KEYWORDS:
        # Word-boundary match to avoid false positives on column names
        # like "created_at" matching "CREATE".
        if re.search(rf"\b{keyword}\b", upper):
            return GuardrailResult(
                allowed=False,
                reason=f"Statement contains forbidden keyword: {keyword}.",
            )

    sanitized = _enforce_row_limit(single_statement, max_rows)
    return GuardrailResult(allowed=True, sanitized_sql=sanitized)


def _enforce_row_limit(sql: str, max_rows: int) -> str:
    """Inject or cap a LIMIT clause."""
    match = re.search(r"\bLIMIT\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if match:
        requested = int(match.group(1))
        if requested > max_rows:
            return re.sub(
                r"\bLIMIT\s+\d+\b", f"LIMIT {max_rows}", sql, flags=re.IGNORECASE
            )
        return sql
    return f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"
