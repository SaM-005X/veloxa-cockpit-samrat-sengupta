"""Portable path-sanitized JSON seed snapshot & offline DB hydration (`db/seed.py`).

Enables 100% deterministic fresh-clone setup and test execution even when the external
`Veloxa_Hackathon_Release_Packs` folder, `DATABASE_URL`, and `GROQ_API_KEY` are absent.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from db.database import REPO_ROOT, DatabaseManager

DEFAULT_SEED_PATH = REPO_ROOT / "data" / "seed" / "veloxa_seed.json"

# Strict foreign-key-safe insertion order across all 21 relational tables
TABLE_ORDER: tuple[str, ...] = (
    "ingestion_runs",
    "employees",
    "reporting_lines",
    "entity_aliases",
    "evidence_index",
    "conflicts",
    "emails",
    "documents",
    "gl_transactions",
    "payroll_summary",
    "payroll_restricted",
    "hiring_reqs",
    "leave_records",
    "pulse_surveys",
    "jira_versions",
    "jira_issues",
    "git_commits",
    "incidents",
    "oncall_rota",
    "agent_profiles",
    "voice_note_decisions",
)

FORBIDDEN_SEED_TOKENS: tuple[str, ...] = (
    "c:\\users",
    "c:\\\\users",
    "/users/",
    "downloads",
    "private_master",
    "handoff",
    "gsk_",
    "postgresql://",
    "postgres://",
)


def _assert_clean_seed_text(raw_json: str) -> None:
    """Fail immediately if any machine path, private doc marker, or credential appears."""
    lowered = raw_json.lower()
    for token in FORBIDDEN_SEED_TOKENS:
        if token in lowered:
            raise ValueError(f"Forbidden token detected in seed export: {token!r}")


def export_seed_snapshot(
    db: DatabaseManager | None = None,
    output_path: Path | str = DEFAULT_SEED_PATH,
) -> dict[str, Any]:
    """Export normalized SQLite tables into a path-sanitized portable JSON seed snapshot."""
    db_mgr = db or DatabaseManager()
    out_file = Path(output_path)

    tables_dict: dict[str, list[dict[str, Any]]] = {}
    table_counts: dict[str, int] = {}

    with db_mgr.sqlite_conn() as conn:
        for tbl in TABLE_ORDER:
            if tbl == "ingestion_runs":
                rows = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM ingestion_runs ORDER BY release_date ASC, release_tag ASC"
                    ).fetchall()
                ]
                sanitized_runs: list[dict[str, Any]] = []
                for idx, row in enumerate(rows, start=1):
                    r_copy = dict(row)
                    r_copy["run_id"] = idx
                    r_copy["source_dir"] = f"portable_seed/{r_copy['release_tag']}"
                    r_copy["loaded_at"] = f"{r_copy['release_date']} 00:00:00"
                    sanitized_runs.append(r_copy)
                tables_dict[tbl] = sanitized_runs
                table_counts[tbl] = len(sanitized_runs)
            else:
                pk_col = conn.execute(f"PRAGMA table_info({tbl})").fetchall()[0]["name"]
                rows = [
                    dict(r)
                    for r in conn.execute(f"SELECT * FROM {tbl} ORDER BY {pk_col} ASC").fetchall()
                ]
                tables_dict[tbl] = rows
                table_counts[tbl] = len(rows)

    payload = {
        "schema_version": "stage5-v1",
        "description": (
            "Portable normalized Day 1-4 Veloxa CXO Cockpit seed snapshot "
            "(no raw archives, machine paths, or secrets)"
        ),
        "tables": tables_dict,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    _assert_clean_seed_text(serialized)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(serialized, encoding="utf-8")

    return {
        "status": "exported",
        "seed_path": str(out_file),
        "total_rows": sum(table_counts.values()),
        "table_counts": table_counts,
        "size_bytes": out_file.stat().st_size,
    }


def load_seed_snapshot(
    db: DatabaseManager | None = None,
    seed_path: Path | str = DEFAULT_SEED_PATH,
    sync_postgres: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Initialize schema and hydrate local SQLite database from portable JSON seed."""
    db_mgr = db or DatabaseManager()
    seed_file = Path(seed_path)
    if not seed_file.is_file():
        raise FileNotFoundError(f"Portable seed snapshot not found: {seed_file}")

    db_mgr.init_schema(sync_postgres=sync_postgres)

    if not force:
        counts = db_mgr.table_counts()
        if counts.get("employees", 0) >= 19 and counts.get("evidence_index", 0) >= 57:
            return {"status": "already_populated", "counts": counts}

    payload = json.loads(seed_file.read_text(encoding="utf-8"))
    tables_data: dict[str, list[dict[str, Any]]] = payload.get("tables", payload)

    with db_mgr.sqlite_conn() as conn:
        for tbl in reversed(TABLE_ORDER):
            conn.execute(f"DELETE FROM {tbl}")

        for tbl in TABLE_ORDER:
            rows = tables_data.get(tbl, [])
            if not rows:
                continue
            valid_cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
            cols = [c for c in valid_cols if c in rows[0]]
            if not cols:
                continue
            placeholders = ", ".join("?" for _ in cols)
            col_list = ", ".join(cols)
            sql = f"INSERT OR REPLACE INTO {tbl} ({col_list}) VALUES ({placeholders})"
            values = [tuple(row.get(c) for c in cols) for row in rows]
            conn.executemany(sql, values)

    return {
        "status": "seeded",
        "seed_path": str(seed_file),
        "counts": db_mgr.table_counts(),
    }


def ensure_populated(
    db: DatabaseManager | None = None,
    seed_path: Path | str = DEFAULT_SEED_PATH,
) -> dict[str, Any]:
    """Ensure SQLite database has schema and seed data if currently empty."""
    db_mgr = db or DatabaseManager()
    if not db_mgr.sqlite_path.is_file():
        db_mgr.init_schema(sync_postgres=False)

    try:
        counts = db_mgr.table_counts()
    except sqlite3.OperationalError:
        db_mgr.init_schema(sync_postgres=False)
        counts = db_mgr.table_counts()

    if (counts.get("employees", 0) == 0 or counts.get("evidence_index", 0) == 0) and Path(seed_path).is_file():
        return load_seed_snapshot(db_mgr, seed_path=seed_path, sync_postgres=False, force=True)

    return {"status": "ready", "counts": counts}
