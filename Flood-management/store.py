import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ["new", "verified", "dispatched", "rescued"]

def get_db_path(path=None):
    if path:
        return path
    env_path = os.environ.get("SANKAT_DB")
    if env_path:
        return env_path
    return str(Path(__file__).resolve().parents[1] / "sankat.db")

def init(path=None):
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS items (
            report_id TEXT PRIMARY KEY,
            label TEXT,
            payload TEXT,
            created_at TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS runs (
            file_hash TEXT PRIMARY KEY,
            label TEXT,
            created_at TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS status (
            report_id TEXT PRIMARY KEY,
            status TEXT,
            updated_at TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT,
            old_status TEXT,
            new_status TEXT,
            operator TEXT,
            at TEXT
        )''')
        conn.commit()
    finally:
        conn.close()

def _now():
    return datetime.now(timezone.utc).isoformat()

def add_items(items, label, file_hash=None, path=None):
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    now = _now()
    try:
        cur = conn.cursor()
        for item in items:
            report_id = item.get("report_id")
            if not report_id:
                continue
            payload = json.dumps(item, ensure_ascii=False)
            cur.execute('''
                INSERT INTO items (report_id, label, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    label=excluded.label,
                    payload=excluded.payload
            ''', (report_id, label, payload, now))
        
        if file_hash:
            cur.execute('''
                INSERT INTO runs (file_hash, label, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(file_hash) DO NOTHING
            ''', (file_hash, label, now))
        conn.commit()
    finally:
        conn.close()

def has_run(file_hash, path=None) -> bool:
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM runs WHERE file_hash = ?", (file_hash,))
        return cur.fetchone() is not None
    finally:
        conn.close()

def load_items(path=None) -> list[dict]:
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload FROM items ORDER BY created_at ASC, rowid ASC")
        return [json.loads(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()

def update_item(report_id, patch: dict, path=None):
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload FROM items WHERE report_id = ?", (report_id,))
        row = cur.fetchone()
        if row:
            item = json.loads(row[0])
            item.update(patch)
            new_payload = json.dumps(item, ensure_ascii=False)
            cur.execute("UPDATE items SET payload = ? WHERE report_id = ?", (new_payload, report_id))
            conn.commit()
    finally:
        conn.close()

def set_status(report_ids, new_status, operator="operator", path=None):
    if new_status not in STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    now = _now()
    try:
        cur = conn.cursor()
        for rid in report_ids:
            cur.execute("SELECT status FROM status WHERE report_id = ?", (rid,))
            row = cur.fetchone()
            old_status = row[0] if row else "new"
            
            cur.execute('''
                INSERT INTO status (report_id, status, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at
            ''', (rid, new_status, now))
            
            cur.execute('''
                INSERT INTO status_log (report_id, old_status, new_status, operator, at)
                VALUES (?, ?, ?, ?, ?)
            ''', (rid, old_status, new_status, operator, now))
        conn.commit()
    finally:
        conn.close()

def get_status_map(path=None) -> dict:
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute("SELECT report_id, status FROM status")
        return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()

def get_status_log(limit=50, path=None) -> list[dict]:
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, report_id, old_status, new_status, operator, at FROM status_log ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def clear_all(path=None):
    db_path = get_db_path(path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM items")
        cur.execute("DELETE FROM runs")
        cur.execute("DELETE FROM status")
        cur.execute("DELETE FROM status_log")
        conn.commit()
    finally:
        conn.close()
