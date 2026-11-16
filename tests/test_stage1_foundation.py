"""Stage 1 foundation tests: schema DDL, SQLite mirror, Point-in-Time isolation, and Day 1 ingestion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from db.database import DatabaseManager
from ingest.day1_loader import ingest_day1
from ingest.temporal import is_visible_as_of, release_date_for_folder


def test_schema_initializes_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "test_veloxa.db"
    db = DatabaseManager(sqlite_path=db_path, database_url="")
    status = db.init_schema(sync_postgres=False)

    assert "initialized" in status["sqlite"]
    counts = db.table_counts()
    expected_tables = {
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
    }
    assert expected_tables.issubset(counts.keys())
    assert all(v == 0 for v in counts.values())


def test_temporal_release_mapping_and_isolation(tmp_path: Path) -> None:
    assert release_date_for_folder("Day1_Mon_16Nov") == "2026-11-16"
    assert release_date_for_folder("Day2_Tue_17Nov") == "2026-11-17"
    assert is_visible_as_of("2026-11-16", "2026-11-16") is True
    assert is_visible_as_of("2026-11-17", "2026-11-16") is False

    db = DatabaseManager(sqlite_path=tmp_path / "pit.db", database_url="")
    db.init_schema(sync_postgres=False)
    with db.sqlite_conn() as conn:
        conn.execute(
            """INSERT INTO evidence_index
            (evidence_id, source_file, source_type, location, fact_text, release_date, reliability)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("E001", "Board_Update_Apr-Jun_2026.pdf", "document", "p1", "Day 1 fact", "2026-11-16", "High"),
        )
        conn.execute(
            """INSERT INTO evidence_index
            (evidence_id, source_file, source_type, location, fact_text, release_date, reliability)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("E002", "Hiring_Tracker.xlsx", "export", "row2", "Day 2 fact", "2026-11-17", "High"),
        )

    day1_rows = db.query(
        "SELECT evidence_id FROM evidence_index WHERE release_date <= ? ORDER BY evidence_id",
        ("2026-11-16",),
    )
    assert [r["evidence_id"] for r in day1_rows] == ["E001"]


def test_day1_loader_parses_fixtures(tmp_path: Path) -> None:
    day1_dir = tmp_path / "Day1_Mon_16Nov"
    day1_dir.mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "employee_id": "VX001",
                "full_name": "Ananya Rao",
                "department": "Executive",
                "title": "CEO",
                "status": "Active",
            },
            {
                "employee_id": "VX004",
                "full_name": "Vikram Menon",
                "department": "Engineering",
                "title": "VP Engineering",
                "status": "Active",
            },
        ]
    ).to_excel(day1_dir / "Employee_Master.xlsx", index=False)

    pd.DataFrame(
        [
            {
                "period_month": "2026-02",
                "employee_id": "VX004",
                "department": "Engineering",
                "gross_inr": 100000,
                "net_inr": 85000,
                "days_paid": 28,
                "days_in_month": 28,
                "prepared_by": "KS",
            },
            {
                "period_month": "2026-02",
                "employee_id": "VX018",
                "department": "Engineering",
                "gross_inr": 110000,
                "net_inr": 95000,
                "days_paid": 28,
                "days_in_month": 28,
                "prepared_by": "KS",
            },
        ]
    ).to_excel(day1_dir / "Payroll_Register_Jan-Mar_2026.xlsx", index=False)

    (day1_dir / "01.eml").write_text(
        "From: Meera Iyer <meera@veloxa.in>\n"
        "To: Karthik <karthik@veloxa.in>\n"
        "Subject: Feb Payroll Handover\n"
        "Date: 2026-02-08\n\n"
        "Please process Feb payroll while Fatima is on leave.\n",
        encoding="utf-8",
    )

    db = DatabaseManager(sqlite_path=tmp_path / "ingest.db", database_url="")
    res = ingest_day1(tmp_path, db=db)

    assert res["release_date"] == "2026-11-16"
    assert res["counts"]["employees"] == 2
    assert res["counts"]["payroll_summary"] == 1
    assert res["counts"]["emails"] == 1

    emps = db.query("SELECT entity_id, is_agent_persona FROM employees ORDER BY entity_id")
    assert emps == [
        {"entity_id": "VX001", "is_agent_persona": 0},
        {"entity_id": "VX004", "is_agent_persona": 1},
    ]

    summary = db.query("SELECT department, headcount, total_gross_inr FROM payroll_summary")
    assert summary == [{"department": "Engineering", "headcount": 2, "total_gross_inr": 210000.0}]
