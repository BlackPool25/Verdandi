"""Incident + symptom store: link downstream fires to open root incidents.

Backend: sqlite in-memory/file (tests, hermetic) or postgres when
DATABASE_URL is set (live docker). Reachability via twin DAG hops.
"""

from __future__ import annotations

import os
import sqlite3
import time


def _connect(url: str | None = None):
    url = url or os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres"):
        import psycopg  # type: ignore[import-untyped]

        return psycopg.connect(url)
    conn = sqlite3.connect(":memory:" if not url else url)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 root_machine TEXT NOT NULL, fault_family TEXT NOT NULL,
 t0_est INTEGER NOT NULL, seed INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'open', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS predicted_cascade(
 incident_id INTEGER REFERENCES incidents(id),
 machine TEXT NOT NULL, pred_tick INTEGER NOT NULL, hop_est INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS symptoms(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 incident_id INTEGER REFERENCES incidents(id),
 machine TEXT NOT NULL, onset_tick INTEGER NOT NULL,
 own_state TEXT NOT NULL, pred_hit INTEGER NOT NULL, linked_at REAL NOT NULL);
"""


class IncidentStore:
    def __init__(self, conn):
        self.conn = conn
        for stmt in _SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(stmt)
        conn.commit()

    @classmethod
    def memory(cls):
        return cls(_connect())

    @classmethod
    def from_env(cls):
        return cls(_connect())

    def create_incident(self, root: str, fault_family: str, t0_est: int, seed: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO incidents(root_machine,fault_family,t0_est,seed,status,created_at)"
            " VALUES(?,?,?,?, 'open',?)",
            (root, fault_family, t0_est, seed, time.time()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_prediction(self, incident_id: int, rows: list[tuple[str, int, int]]) -> None:
        self.conn.executemany(
            "INSERT INTO predicted_cascade(incident_id,machine,pred_tick,hop_est)"
            " VALUES(?,?,?,?)",
            [(incident_id, m, t, h) for m, t, h in rows],
        )
        self.conn.commit()

    def link_or_create(
        self, machine: str, onset_tick: int, own_state: str, seed: int,
        h: int = 150, slack: int = 25,
    ) -> tuple[int, bool]:
        from src.twin import compute_hop

        rows = self.conn.execute(
            "SELECT id,root_machine,t0_est FROM incidents"
            " WHERE seed=? AND status='open'",
            (seed,),
        ).fetchall()
        for inc_id, root, t0 in rows:
            if compute_hop(root, machine, max_depth=3) is None:
                continue
            if not (t0 <= onset_tick <= t0 + h + slack):
                continue
            pred = self.conn.execute(
                "SELECT 1 FROM predicted_cascade WHERE incident_id=? AND machine=?",
                (inc_id, machine),
            ).fetchone()
            self.conn.execute(
                "INSERT INTO symptoms(incident_id,machine,onset_tick,own_state,pred_hit,linked_at)"
                " VALUES(?,?,?,?,?,?)",
                (inc_id, machine, onset_tick, own_state, 1 if pred else 0, time.time()),
            )
            self.conn.commit()
            return int(inc_id), True
        new_id = self.create_incident(machine, "unknown", onset_tick, seed)
        self.conn.execute(
            "INSERT INTO symptoms(incident_id,machine,onset_tick,own_state,pred_hit,linked_at)"
            " VALUES(?,?,?,?,?,?)",
            (new_id, machine, onset_tick, own_state, 0, time.time()),
        )
        self.conn.commit()
        return new_id, False
