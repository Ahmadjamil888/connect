import json
import sqlite3
from datetime import datetime
from pathlib import Path


def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, goal TEXT, started_at TEXT, workspace TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, session_id INTEGER, type TEXT, content TEXT, ts TEXT)"
    )
    conn.commit()
    return conn


def log_session(db_path, goal, workspace) -> int:
    conn = init_db(db_path)
    cur = conn.execute(
        "INSERT INTO sessions (goal, started_at, workspace) VALUES (?, ?, ?)",
        (goal, datetime.utcnow().isoformat(), workspace),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def log_event(db_path, session_id, type, content):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO events (session_id, type, content, ts) VALUES (?, ?, ?, ?)",
        (session_id, type, json.dumps(content), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_recent_sessions(db_path, n=10) -> list[dict]:
    conn = init_db(db_path)
    cur = conn.execute(
        "SELECT id, goal, started_at, workspace FROM sessions ORDER BY id DESC LIMIT ?",
        (n,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": row[0], "goal": row[1], "started_at": row[2], "workspace": row[3]}
        for row in rows
    ]
