"""Schema introspection.

Reads the *real* structure of the connected database (tables, columns, types,
foreign keys) so that SQL generation is grounded in facts rather than the
LLM guessing column names from the question alone. This directly addresses
gap #3 from our baseline analysis ("no schema-aware grounding").
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[tuple[str, str, str]] = field(default_factory=list)
    # (local_column, referenced_table, referenced_column)

    def to_prompt_block(self) -> str:
        """Render this table as a compact block for the LLM prompt."""
        col_lines = []
        for c in self.columns:
            marker = " PRIMARY KEY" if c.is_primary_key else ""
            col_lines.append(f"    {c.name} {c.data_type}{marker}")
        fk_lines = [
            f"    FOREIGN KEY ({local}) REFERENCES {ref_table}({ref_col})"
            for local, ref_table, ref_col in self.foreign_keys
        ]
        body = ",\n".join(col_lines + fk_lines)
        return f"TABLE {self.name} (\n{body}\n)"


class SchemaReader:
    """Reads schema metadata from a SQLite database.

    Kept intentionally small and swappable: production use with Postgres/
    MySQL would implement the same interface against information_schema.
    """

    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection

    def read_all_tables(self) -> list[TableInfo]:
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
        table_names = [row[0] for row in cursor.fetchall()]
        return [self._read_table(name) for name in table_names]

    def _read_table(self, table_name: str) -> TableInfo:
        # NOTE: table_name here always originates from sqlite_master above,
        # never from user/LLM input, so building the PRAGMA string this way
        # is safe. User/LLM-supplied SQL never reaches this method.
        cols_cursor = self._conn.execute(f"PRAGMA table_info('{table_name}')")
        columns = [
            ColumnInfo(
                name=row[1],
                data_type=row[2] or "TEXT",
                is_nullable=not bool(row[3]),
                is_primary_key=bool(row[5]),
            )
            for row in cols_cursor.fetchall()
        ]

        fk_cursor = self._conn.execute(f"PRAGMA foreign_key_list('{table_name}')")
        foreign_keys = [(row[3], row[2], row[4]) for row in fk_cursor.fetchall()]

        return TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys)

    def render_schema_prompt(self) -> str:
        """Full schema as a single string, ready to inject into an LLM prompt."""
        tables = self.read_all_tables()
        if not tables:
            return "-- No tables found in this database."
        return "\n\n".join(t.to_prompt_block() for t in tables)
