"""Creates a small example SQLite database for demos and local testing."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "example.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS orders;

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            country TEXT
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product TEXT,
            total REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        INSERT INTO customers (id, name, country) VALUES
            (1, 'Ada Lovelace', 'UK'),
            (2, 'Grace Hopper', 'USA'),
            (3, 'Alan Turing', 'UK');

        INSERT INTO orders (id, customer_id, product, total) VALUES
            (1, 1, 'Compiler License', 199.99),
            (2, 2, 'Debugger Pro', 49.99),
            (3, 1, 'Analytical Engine Manual', 12.50),
            (4, 3, 'Enigma Toolkit', 89.00);
        """
    )
    conn.commit()
    conn.close()
    print(f"Seeded example database at {DB_PATH}")


if __name__ == "__main__":
    main()
