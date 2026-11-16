"""Stage 1 foundation tests: schema DDL, SQLite mirror, Point-in-Time isolation, and Day 1 ingestion."""

from __future__ import annotations

import os
from pathlib import Path

import openpyxl
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
        conn.execute(
            """INSERT INTO conflicts
            (conflict_id, topic, claim_a_evidence_id, claim_b_evidence_id, summary, release_date)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("C_DAY1", "Headcount", "E001", "E001", "Day 1 conflict", "2026-11-16"),
        )
        conn.execute(
            """INSERT INTO conflicts
            (conflict_id, topic, claim_a_evidence_id, claim_b_evidence_id, summary, release_date)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("C_DAY2", "Hiring", "E002", "E002", "Day 2 conflict", "2026-11-17"),
        )

    day1_rows = db.query(
        "SELECT evidence_id FROM evidence_index WHERE release_date <= ? ORDER BY evidence_id",
        ("2026-11-16",),
    )
    assert [r["evidence_id"] for r in day1_rows] == ["E001"]

    day1_conflicts = db.query(
        "SELECT conflict_id FROM conflicts WHERE release_date <= ? ORDER BY conflict_id",
        ("2026-11-16",),
    )
    assert [r["conflict_id"] for r in day1_conflicts] == ["C_DAY1"]


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


def _write_banner_xlsx(path: Path, sheet_name: str, banner: str, headers: list[str], rows: list[list[object]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append([banner])
    ws.append([])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_day1_loader_handles_real_preamble_and_payroll_join(tmp_path: Path) -> None:
    """Verify Row-3 header detection, Payroll->Employee department join, proration flag, and RFC 2822 email date."""
    day1_dir = tmp_path / "Day1_Mon_16Nov"
    day1_dir.mkdir(parents=True)

    _write_banner_xlsx(
        day1_dir / "Employee_Master.xlsx",
        "Employees",
        "Keka HRMS export",
        ["Emp ID", "Full Name", "Work Email", "Department", "Title", "Manager ID", "Join Date", "Location", "Status", "Exit Date"],
        [
            ["VX010", "Karthik Subramanian", "karthik.s@veloxa.in", "Finance", "FP&A Manager", "VX003", "2024-10-01", "Bengaluru", "Active", ""],
            ["VX018", "Rahul Verma", "rahul.v@veloxa.in", "Engineering", "Backend Engineer", "VX004", "2026-02-03", "Bengaluru", "Active", ""],
        ],
    )

    _write_banner_xlsx(
        day1_dir / "Payroll_Register_Jan-Mar_2026.xlsx",
        "Payroll Q4",
        "Payroll register, Jan to Mar 2026",
        ["Emp ID", "Name", "Month", "Days in Month", "Days Payable", "Gross (Rs.)", "Deductions (Rs.)", "Net (Rs.)", "Processed By"],
        [
            ["VX010", "Karthik Subramanian", "Feb-2026", 28, 28, 140000, 16800, 123200, "KS"],
            ["VX018", "Rahul Verma", "Feb-2026", 28, 28, 110000, 13200, 96800, "KS"],
        ],
    )

    _write_banner_xlsx(
        day1_dir / "GL_Export_Apr-Sep_2026.xlsx",
        "GL Apr-Sep",
        "General ledger export, Zoho Books",
        ["Txn Date", "Voucher", "Vendor / Payee", "Ref", "Cost Centre", "Amount (Rs.)", "Narration", "Entered By"],
        [
            ["2026-08-29", "JV-0846", "Sapphire Events Pvt Ltd", "INV-2291", "MKT-EVT", 542800, "Summit: venue, AV", "FS"],
            ["2026-09-11", "JV-0918", "Sapphire Residency Hotel", "SRH/26/4471", "SAL-TRV", 38940, "Sales offsite", "FS"],
        ],
    )

    (day1_dir / "01.eml").write_text(
        "From: Karthik Subramanian <karthik.s@veloxa.in>\n"
        "To: Meera Iyer <meera@veloxa.in>\n"
        "Subject: Feb payroll done\n"
        "Date: Sat, 28 Feb 2026 20:15:00 +0530\n\n"
        "Ran Feb payroll.\n",
        encoding="utf-8",
    )

    db = DatabaseManager(sqlite_path=tmp_path / "real_fmt.db", database_url="")
    res = ingest_day1(tmp_path, db=db)

    assert res["counts"]["employees"] == 2
    assert res["counts"]["gl_transactions"] == 2
    assert res["counts"]["payroll_summary"] == 2

    summary = db.query(
        "SELECT period_month, department, headcount, total_gross_inr FROM payroll_summary ORDER BY department"
    )
    assert summary == [
        {"period_month": "2026-02", "department": "Engineering", "headcount": 1, "total_gross_inr": 110000.0},
        {"period_month": "2026-02", "department": "Finance", "headcount": 1, "total_gross_inr": 140000.0},
    ]

    anomalies = db.query(
        "SELECT employee_id, anomaly_flag FROM payroll_restricted WHERE anomaly_flag != ''"
    )
    assert len(anomalies) == 1
    assert anomalies[0]["employee_id"] == "VX018"
    assert "PRORATION_OVERPAYMENT" in anomalies[0]["anomaly_flag"]

    emails = db.query("SELECT email_id, sender_entity_id, event_date FROM emails")
    assert emails == [{"email_id": "01", "sender_entity_id": "VX010", "event_date": "2026-02-28"}]


def test_real_day1_pack_counts_and_payroll_privacy(tmp_path: Path) -> None:
    """Verify exact counts and payroll privacy on the real Day1_Mon_16Nov data pack when mounted."""
    data_dir = Path(os.getenv("VELOXA_DATA_DIR", "").strip())
    if not data_dir.exists() or not (data_dir / "Day1_Mon_16Nov").exists():
        pytest.skip("Real Day1_Mon_16Nov pack not mounted in this environment")

    db = DatabaseManager(sqlite_path=tmp_path / "day1_real.db", database_url="")
    res = ingest_day1(data_dir, db=db)

    assert res["release_date"] == "2026-11-16"
    assert res["files_loaded"] == 15
    assert res["counts"] == {
        "employees": 19,
        "reporting_lines": 19,
        "gl_transactions": 28,
        "payroll_summary": 21,
        "payroll_restricted": 56,
        "entity_aliases": 22,
        "evidence_index": 21,
        "conflicts": 5,
        "emails": 3,
        "documents": 8,
    }

    # Verify 14 agent personas
    persona_cnt = db.query("SELECT SUM(is_agent_persona) AS cnt FROM employees")[0]["cnt"]
    assert persona_cnt == 14

    # Verify monthly payroll summary totals match GL PAYROLL (31,75,000 for Feb/Mar)
    monthly = db.query(
        "SELECT period_month, SUM(headcount) AS hc, SUM(total_gross_inr) AS gross "
        "FROM payroll_summary GROUP BY period_month ORDER BY period_month"
    )
    assert monthly == [
        {"period_month": "2026-01", "hc": 18, "gross": 3065000.0},
        {"period_month": "2026-02", "hc": 19, "gross": 3175000.0},
        {"period_month": "2026-03", "hc": 19, "gross": 3175000.0},
    ]

    # Verify payroll_summary schema contains no individual identifiers (CFO T2 rule)
    cols = {r["name"] for r in db.query("PRAGMA table_info(payroll_summary)")}
    assert "employee_id" not in cols
    assert "full_name" not in cols
