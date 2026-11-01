"""SQLite storage for watched folders, automation runs and every file move (for undo)."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("automation.db")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as c:
        c.executescript(
            """CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                interval_minutes INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run TEXT);
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path TEXT NOT NULL,
                started_at TEXT NOT NULL,
                trigger TEXT NOT NULL,
                moved_count INTEGER NOT NULL,
                bytes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'done');
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                src TEXT NOT NULL, dst TEXT NOT NULL,
                category TEXT NOT NULL, size INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_moves_run ON moves(run_id);"""
        )
