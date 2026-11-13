import os
import sqlite3
from collections.abc import Iterator

from . import seed

SCHEMA = """
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, industry TEXT, website TEXT
);
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT, phone TEXT,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL
);
CREATE TABLE deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
    stage TEXT NOT NULL DEFAULT 'lead',
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL
);
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, due_date TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL
);
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL, created_at TEXT NOT NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL
);
"""

TABLES = ["notes", "tasks", "deals", "contacts", "companies"]


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO companies (name, industry, website) VALUES (?,?,?)", seed.COMPANIES
    )
    conn.executemany(
        "INSERT INTO contacts (name, email, phone, company_id) VALUES (?,?,?,?)", seed.contacts()
    )
    conn.executemany(
        "INSERT INTO deals (title, amount, stage, company_id, contact_id) VALUES (?,?,?,?,?)",
        seed.deals(),
    )
    conn.executemany(
        "INSERT INTO tasks (title, due_date, done, contact_id, company_id) VALUES (?,?,?,?,?)",
        seed.tasks(),
    )
    conn.executemany(
        "INSERT INTO notes (body, created_at, contact_id, company_id) VALUES (?,?,?,?)",
        seed.notes(),
    )


def reset_db(db_path: str) -> None:
    conn = connect(db_path)
    try:
        for table in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.executescript(SCHEMA)
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    """Seed the DB if it has no tables yet."""
    if os.path.exists(db_path):
        conn = connect(db_path)
        try:
            found = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='companies'"
            ).fetchone()
        finally:
            conn.close()
        if found:
            return
    reset_db(db_path)
