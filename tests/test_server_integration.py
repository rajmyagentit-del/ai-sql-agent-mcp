"""Integration tests for the full ask_database pipeline.

These monkeypatch the LLM client factory so the whole tool logic (schema
introspection -> generation -> guardrails -> execution -> response shape)
is exercised end-to-end without any network call or API key.
"""

import sqlite3

import pytest

from ai_sql_agent_mcp import server as server_module


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, reply):
        self._reply = reply

    def create(self, **kwargs):
        return _FakeResponse(self._reply)


class _FakeClient:
    def __init__(self, reply):
        self.messages = _FakeMessages(reply)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO customers (id, name) VALUES (1, 'Ada'), (2, 'Grace');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(server_module, "DB_PATH", str(db_path))
    return db_path


def _patch_llm(monkeypatch, reply_sql: str):
    monkeypatch.setattr(
        server_module, "build_client_from_env", lambda: _FakeClient(reply_sql)
    )


def test_ask_database_success(temp_db, monkeypatch):
    _patch_llm(monkeypatch, "SELECT * FROM customers")
    result = server_module.ask_database("show all customers")
    assert result["ok"] is True
    assert result["rows"] == [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]
    assert "LIMIT" in result["sql"]


def test_ask_database_rejects_write_query(temp_db, monkeypatch):
    _patch_llm(monkeypatch, "DELETE FROM customers")
    result = server_module.ask_database("delete everyone")
    assert result["ok"] is False
    assert result["error"] == "rejected_by_guardrails"


def test_ask_database_cannot_answer(temp_db, monkeypatch):
    _patch_llm(monkeypatch, "CANNOT_ANSWER: no such table")
    result = server_module.ask_database("show me spaceship inventory")
    assert result["ok"] is False
    assert result["error"] == "cannot_answer"


def test_ask_database_requires_valid_token_when_configured(temp_db, monkeypatch):
    monkeypatch.setattr(server_module, "API_TOKEN", "secret123")
    _patch_llm(monkeypatch, "SELECT * FROM customers")

    unauthorized = server_module.ask_database("show all customers", api_token="wrong")
    assert unauthorized["ok"] is False
    assert unauthorized["error"] == "unauthorized"

    authorized = server_module.ask_database("show all customers", api_token="secret123")
    assert authorized["ok"] is True


def test_describe_schema(temp_db):
    result = server_module.describe_schema()
    assert result["ok"] is True
    table_names = {t["name"] for t in result["tables"]}
    assert "customers" in table_names
