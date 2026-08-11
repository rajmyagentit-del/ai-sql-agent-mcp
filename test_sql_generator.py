import pytest

from ai_sql_agent_mcp.sql_generator import SQLGenerationError, SQLGenerator


class _FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, reply: str):
        self._reply = reply
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeResponse(self._reply)


class _FakeClient:
    def __init__(self, reply: str):
        self.messages = _FakeMessages(reply)


def test_generates_plain_sql():
    client = _FakeClient("SELECT * FROM customers")
    generator = SQLGenerator(client)
    sql = generator.generate("show me all customers", "TABLE customers (...)")
    assert sql == "SELECT * FROM customers"


def test_strips_markdown_fences():
    client = _FakeClient("```sql\nSELECT * FROM customers\n```")
    generator = SQLGenerator(client)
    sql = generator.generate("show me all customers", "TABLE customers (...)")
    assert sql == "SELECT * FROM customers"


def test_raises_on_cannot_answer():
    client = _FakeClient("CANNOT_ANSWER: no matching table in schema")
    generator = SQLGenerator(client)
    with pytest.raises(SQLGenerationError, match="no matching table"):
        generator.generate("show me spaceships", "TABLE customers (...)")


def test_raises_on_empty_response():
    client = _FakeClient("")
    generator = SQLGenerator(client)
    with pytest.raises(SQLGenerationError):
        generator.generate("anything", "TABLE customers (...)")


def test_schema_is_injected_into_system_prompt():
    client = _FakeClient("SELECT * FROM customers")
    generator = SQLGenerator(client)
    generator.generate("show me all customers", "TABLE customers (id, name)")
    system_prompt = client.messages.last_call_kwargs["system"]
    assert "TABLE customers (id, name)" in system_prompt
