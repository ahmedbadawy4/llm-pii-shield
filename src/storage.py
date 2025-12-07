import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List


def init_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                pii_types TEXT NOT NULL,
                model TEXT,
                latency REAL,
                original_length INTEGER,
                masked_length INTEGER
            )
            """
        )
        conn.commit()


def record_request(path: Path, payload: Dict[str, Any]) -> None:
    pii_types = json.dumps(payload.get("pii_types", []))
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO requests (id, timestamp, pii_types, model, latency, original_length, masked_length)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["id"],
                payload["timestamp"],
                pii_types,
                payload.get("model"),
                payload.get("latency"),
                payload.get("original_length"),
                payload.get("masked_length"),
            ),
        )
        conn.commit()


def fetch_stats(path: Path, limit: int = 20) -> Dict[str, Any]:
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        total_requests = conn.execute(
            "SELECT COUNT(*) as count FROM requests"
        ).fetchone()["count"]
        pii_rows = conn.execute("SELECT pii_types FROM requests").fetchall()

        pii_counter: Counter[str] = Counter()
        for row in pii_rows:
            for pii_type in json.loads(row["pii_types"]):
                pii_counter[pii_type] += 1

        recent_rows = conn.execute(
            """
            SELECT id, timestamp, pii_types, model, latency, original_length, masked_length
            FROM requests
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        recent_events: List[Dict[str, Any]] = []
        for row in recent_rows:
            recent_events.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "pii_types": json.loads(row["pii_types"]),
                    "model": row["model"],
                    "latency": row["latency"],
                    "original_length": row["original_length"],
                    "masked_length": row["masked_length"],
                }
            )

    return {
        "total_requests": total_requests,
        "pii_counts": dict(pii_counter),
        "recent_events": recent_events,
    }
