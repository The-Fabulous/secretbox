"""SQLite connections and schema initialization."""
import sqlite3
from contextlib import closing

from .config import DB_FILE


def connect_db():
    return closing(sqlite3.connect(DB_FILE))


def init_db():
    with connect_db() as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS menu_metadata (
                    shop_name TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL
                )
                """
            )
