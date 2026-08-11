import sqlite3

import pytest

from ai_sql_agent_mcp.schema_reader import SchemaReader


@pytest.fixture
def sample_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            total REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        """
    )
    yield conn
    conn.close()


def test_reads_all_tables(sample_db):
    tables = SchemaReader(sample_db).read_all_tables()
    names = {t.name for t in tables}
    assert names == {"customers", "orders"}


def test_reads_columns_and_primary_key(sample_db):
    tables = {t.name: t for t in SchemaReader(sample_db).read_all_tables()}
    id_col = next(c for c in tables["customers"].columns if c.name == "id")
    assert id_col.is_primary_key is True
    assert id_col.data_type == "INTEGER"


def test_reads_foreign_keys(sample_db):
    tables = {t.name: t for t in SchemaReader(sample_db).read_all_tables()}
    assert tables["orders"].foreign_keys == [("customer_id", "customers", "id")]


def test_render_schema_prompt_contains_table_names(sample_db):
    prompt = SchemaReader(sample_db).render_schema_prompt()
    assert "TABLE customers" in prompt
    assert "TABLE orders" in prompt
    assert "FOREIGN KEY (customer_id) REFERENCES customers(id)" in prompt


def test_empty_database_returns_placeholder():
    conn = sqlite3.connect(":memory:")
    prompt = SchemaReader(conn).render_schema_prompt()
    assert "No tables" in prompt
    conn.close()
