import sqlite3
import json
from typing import List, Optional, Dict, Any
from .config import DB_PATH
from .models import RequestItem


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            location_text TEXT,
            lat REAL,
            lon REAL,
            tier TEXT,
            score INTEGER,
            people_count INTEGER,
            vulnerable_tags TEXT,
            water_level TEXT,
            status TEXT DEFAULT 'new',
            duplicate_count INTEGER DEFAULT 0,
            contact TEXT,
            landmark_matched TEXT,
            timestamp TEXT,
            raw_excerpt TEXT,
            is_exact_address INTEGER DEFAULT 1,
            address_note TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dedupe_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            primary_request_id TEXT,
            duplicate_raw_text TEXT,
            similarity_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration helper for existing columns
    try:
        cur.execute("ALTER TABLE requests ADD COLUMN is_exact_address INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE requests ADD COLUMN address_note TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


def clear_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM requests")
    cur.execute("DELETE FROM dedupe_log")
    conn.commit()
    conn.close()


def save_or_update_request(item: RequestItem) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO requests (
            id, location_text, lat, lon, tier, score, people_count,
            vulnerable_tags, water_level, status, duplicate_count,
            contact, landmark_matched, timestamp, raw_excerpt,
            is_exact_address, address_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            score = excluded.score,
            tier = excluded.tier,
            people_count = excluded.people_count,
            duplicate_count = excluded.duplicate_count,
            vulnerable_tags = excluded.vulnerable_tags,
            water_level = excluded.water_level,
            status = excluded.status,
            is_exact_address = excluded.is_exact_address,
            address_note = excluded.address_note
    """, (
        item.id,
        item.location_text,
        item.lat,
        item.lon,
        item.tier,
        item.score,
        item.people_count,
        json.dumps(item.vulnerable_tags),
        item.water_level,
        item.status,
        item.duplicate_count,
        item.contact,
        item.landmark_matched,
        item.timestamp,
        item.raw_excerpt,
        1 if item.is_exact_address else 0,
        item.address_note
    ))
    conn.commit()
    conn.close()


def update_status(req_id: str, new_status: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE requests SET status = ? WHERE id = ?", (new_status, req_id))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def log_dedupe(primary_id: str, raw_text: str, similarity: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO dedupe_log (primary_request_id, duplicate_raw_text, similarity_score)
        VALUES (?, ?, ?)
    """, (primary_id, raw_text, similarity))
    conn.commit()
    conn.close()


def get_all_requests() -> List[RequestItem]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM requests ORDER BY score DESC")
    rows = cur.fetchall()
    conn.close()

    items = []
    for r in rows:
        tags = []
        if r["vulnerable_tags"]:
            try:
                tags = json.loads(r["vulnerable_tags"])
            except Exception:
                tags = []
        
        # Check columns
        is_exact = bool(r["is_exact_address"]) if "is_exact_address" in r.keys() and r["is_exact_address"] is not None else True
        addr_note = r["address_note"] if "address_note" in r.keys() and r["address_note"] else ("Exact address pinpointed" if is_exact else "Not exact address provided (Centered on Main Area)")

        items.append(RequestItem(
            id=r["id"],
            location_text=r["location_text"] or "",
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            tier=r["tier"],
            score=int(r["score"]),
            people_count=int(r["people_count"] or 1),
            vulnerable_tags=tags,
            water_level=r["water_level"] or "unknown",
            status=r["status"] or "new",
            duplicate_count=int(r["duplicate_count"] or 0),
            contact=r["contact"],
            landmark_matched=r["landmark_matched"],
            timestamp=r["timestamp"],
            raw_excerpt=r["raw_excerpt"],
            is_exact_address=is_exact,
            address_note=addr_note
        ))
    return items


def get_total_duplicate_count() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT SUM(duplicate_count) as total_dupes FROM requests")
    row = cur.fetchone()
    total = row["total_dupes"] if row and row["total_dupes"] else 0
    conn.close()
    return int(total)
