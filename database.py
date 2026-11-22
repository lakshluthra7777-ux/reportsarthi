# Database helper functions, using Python's built-in sqlite3 module and plain SQL.

import sqlite3

from flask import current_app, g


def get_db():
    """Return one database connection per request (stored in Flask's `g`)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # lets us use row["name"] instead of row[1]
        g.db.execute("PRAGMA foreign_keys = ON")  # SQLite needs this for ON DELETE CASCADE
    return g.db


def close_db(error=None):
    """Close the connection at the end of every request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables from schema.sql (safe to run more than once)."""
    db = get_db()
    with current_app.open_resource("schema.sql") as file:
        db.executescript(file.read().decode("utf-8"))
    migrate(db)
    db.commit()


def migrate(db):
    """Upgrade a database made by an older version of the app.

    CREATE TABLE IF NOT EXISTS never changes a table that already exists, so a column
    added later must be added with ALTER TABLE. This is a tiny "schema migration".
    """
    columns = [row["name"] for row in db.execute("PRAGMA table_info(results)")]
    if "corrected" not in columns:
        db.execute("ALTER TABLE results ADD COLUMN corrected INTEGER NOT NULL DEFAULT 0")
