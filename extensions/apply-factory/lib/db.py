"""Thin sqlite3 wrapper. Row factory = dict-like access."""
import sqlite3
import sys
from pathlib import Path
from contextlib import contextmanager


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def require_initialized(db_path: str) -> None:
    """Exit with a helpful hint instead of a raw 'no such table' error.

    sqlite3.connect() silently creates an empty file, so a missing or
    schema-less DB otherwise surfaces as sqlite3.OperationalError on the
    first query — confusing on a fresh clone where only `init` has ever
    created the schema.
    """
    p = Path(db_path)
    if p.exists() and p.stat().st_size > 0:
        with connect(db_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kb_entries'"
            ).fetchone()
        if row:
            return
    sys.exit(f"KB not initialized ({db_path}). Run: python orchestrator.py init")


def init(db_path: str, schema_sql: str) -> None:
    schema = Path(schema_sql).read_text()
    with connect(db_path) as conn:
        conn.executescript(schema)


@contextmanager
def tx(db_path: str):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
