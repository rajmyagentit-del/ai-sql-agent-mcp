"""LLM-based natural-language-to-SQL generation.

Grounds every generation call in the real database schema (see
schema_reader.py) rather than letting the model guess table/column names.
"""

from __future__ import annotations

import os
import re

_SYSTEM_PROMPT_TEMPLATE = """You translate natural language questions into a \
single read-only SQLite SELECT statement.

Rules:
- Use ONLY the tables and columns listed in the schema below. Never invent \
column or table names.
- Output ONLY the SQL statement. No explanation, no markdown fences.
- Only generate SELECT statements. Never INSERT, UPDATE, DELETE, DROP, or \
any other write/DDL statement.
- If the question cannot be answered with the given schema, output exactly:
  CANNOT_ANSWER: <short reason>

Schema:
{schema}
"""


class SQLGenerationError(Exception):
    """Raised when the model cannot produce a usable SQL statement."""


def _extract_sql(raw_text: str) -> str:
    """Strip markdown fences/whitespace the model might still add."""
    text = raw_text.strip()
    fence_match = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return text


class SQLGenerator:
    """Wraps an LLM call to generate SQL grounded in the real schema.

    The Anthropic client is injected so it can be swapped for a fake/mock
    client in tests without any network calls.
    """

    def __init__(self, client, model: str = "claude-sonnet-4-6"):
        self._client = client
        self._model = model

    def generate(self, question: str, schema_prompt: str) -> str:
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(schema=schema_prompt)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )

        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        sql = _extract_sql(raw_text)

        if sql.startswith("CANNOT_ANSWER"):
            raise SQLGenerationError(sql.removeprefix("CANNOT_ANSWER:").strip())
        if not sql:
            raise SQLGenerationError("Model returned an empty response.")

        return sql


def build_client_from_env():
    """Create an Anthropic client using ANTHROPIC_API_KEY from the environment.

    Kept as a thin factory so the server module doesn't import anthropic
    directly, and so tests never need a real API key.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Set it as an environment variable "
            "or GitHub Secret before running the server."
        )
    return anthropic.Anthropic(api_key=api_key)
