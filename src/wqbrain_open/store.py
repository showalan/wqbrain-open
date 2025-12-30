from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS formulas (
            formula_id      INTEGER PRIMARY KEY,
            raw_formula     TEXT NOT NULL,
            normalized      TEXT NOT NULL,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            formula_id          INTEGER PRIMARY KEY,
            status              TEXT NOT NULL,
            attempts            INTEGER NOT NULL,
            last_error          TEXT,
            simulation_url      TEXT,
            alpha_platform_id   TEXT,
            alpha_url           TEXT,
            sharpe              REAL,
            fitness             REAL,
            turnover            REAL,
            weight_check        TEXT,
            subsharpe           REAL,
            self_corr           REAL,
            effective_formula   TEXT,
            checks_json         TEXT,
            updated_at          REAL NOT NULL,
            FOREIGN KEY(formula_id) REFERENCES formulas(formula_id)
        );
        """
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);")
    conn.commit()


def upsert_formula(conn: sqlite3.Connection, *, formula_id: int, raw: str, normalized: str) -> None:
    now = time.time()
    conn.execute(
        """
        INSERT INTO formulas(formula_id, raw_formula, normalized, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(formula_id) DO UPDATE SET
            raw_formula=excluded.raw_formula,
            normalized=excluded.normalized,
            updated_at=excluded.updated_at;
        """,
        (formula_id, raw, normalized, now, now),
    )

    conn.execute(
        """
        INSERT INTO runs(formula_id, status, attempts, updated_at)
        VALUES(?, 'PENDING', 0, ?)
        ON CONFLICT(formula_id) DO NOTHING;
        """,
        (formula_id, now),
    )
    conn.commit()


def get_run_status(conn: sqlite3.Connection, *, formula_id: int) -> Optional[str]:
    row = conn.execute("SELECT status FROM runs WHERE formula_id=?", (formula_id,)).fetchone()
    return row["status"] if row else None


def mark_attempt(conn: sqlite3.Connection, *, formula_id: int) -> int:
    now = time.time()
    conn.execute(
        """
        UPDATE runs
        SET attempts = attempts + 1,
            updated_at = ?
        WHERE formula_id = ?;
        """,
        (now, formula_id),
    )
    conn.commit()
    row = conn.execute("SELECT attempts FROM runs WHERE formula_id=?", (formula_id,)).fetchone()
    return int(row["attempts"]) if row else 0


def mark_success(conn: sqlite3.Connection, *, formula_id: int, result: dict[str, Any]) -> None:
    now = time.time()
    conn.execute(
        """
        UPDATE runs
        SET status='SUCCESS',
            last_error=NULL,
            simulation_url=?,
            alpha_platform_id=?,
            alpha_url=?,
            sharpe=?,
            fitness=?,
            turnover=?,
            weight_check=?,
            subsharpe=?,
            self_corr=?,
            effective_formula=?,
            checks_json=?,
            updated_at=?
        WHERE formula_id=?;
        """,
        (
            result.get("simulation_url"),
            result.get("alpha_platform_id"),
            result.get("alpha_url"),
            result.get("sharpe"),
            result.get("fitness"),
            result.get("turnover"),
            result.get("weight_check"),
            result.get("subsharpe"),
            result.get("self_corr"),
            result.get("effective_formula"),
            json.dumps(result.get("checks"), ensure_ascii=False),
            now,
            formula_id,
        ),
    )
    conn.commit()


def mark_error(conn: sqlite3.Connection, *, formula_id: int, status: str, error: str) -> None:
    now = time.time()
    conn.execute(
        """
        UPDATE runs
        SET status=?,
            last_error=?,
            updated_at=?
        WHERE formula_id=?;
        """,
        (status, (error or "")[:5000], now, formula_id),
    )
    conn.commit()


def list_to_run(conn: sqlite3.Connection, *, force: bool) -> list[int]:
    if force:
        rows = conn.execute("SELECT formula_id FROM formulas ORDER BY formula_id").fetchall()
        return [int(r["formula_id"]) for r in rows]

    rows = conn.execute(
        """
        SELECT f.formula_id
        FROM formulas f
        JOIN runs r ON r.formula_id = f.formula_id
        WHERE r.status IN ('PENDING', 'ERROR', 'THROTTLED')
        ORDER BY f.formula_id;
        """
    ).fetchall()
    return [int(r["formula_id"]) for r in rows]


def get_formula(conn: sqlite3.Connection, *, formula_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT f.formula_id, f.raw_formula, f.normalized, r.attempts, r.status
        FROM formulas f
        JOIN runs r ON r.formula_id = f.formula_id
        WHERE f.formula_id = ?;
        """,
        (formula_id,),
    ).fetchone()
    if not row:
        raise KeyError(formula_id)
    return dict(row)
