"""Stage 2 tests: Day 2 ingestion, Point-in-Time isolation, Risk Engine (T6a), and anonymity guardrails."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cockpit.risk_engine import get_ranked_worries
from db.database import DatabaseManager
from ingest.day2_loader import ingest_day2
from ingest.temporal import is_visible_as_of


@pytest.fixture
def test_db() -> DatabaseManager:
    """Use active local SQLite database populated with Day 1 & Day 2 data."""
    db = DatabaseManager()
    return db


def test_day2_ingestion_counts(test_db: DatabaseManager) -> None:
    counts = test_db.table_counts()
    assert counts["hiring_reqs"] == 6
    assert counts["leave_records"] == 19
    assert counts["pulse_surveys"] == 24
    assert counts["emails"] >= 7  # 3 (Day 1) + 4 (Day 2)
    assert counts["documents"] >= 11  # 8 (Day 1) + 3 (Day 2)
    assert counts["evidence_index"] >= 35  # 21 (Day 1) + 14 (Day 2)
    assert counts["conflicts"] >= 8  # 5 (Day 1) + 3 (Day 2)
    assert counts["voice_note_decisions"] >= 1


def test_hiring_tracker_contents(test_db: DatabaseManager) -> None:
    reqs = test_db.query("SELECT * FROM hiring_reqs ORDER BY req_id")
    req_map = {r["req_id"]: r for r in reqs}

    assert "REQ-011" in req_map
    assert "REQ-013" in req_map
    assert "REQ-014" in req_map
    assert "REQ-015" in req_map
    assert "REQ-016" in req_map
    assert "REQ-017" in req_map
    # REQ-012 is notably missing from Keka Hire export
    assert "REQ-012" not in req_map

    # REQ-014 & REQ-015 on hold on 2026-08-12 with 3 & 5 candidates
    assert req_map["REQ-014"]["status"] == "On hold"
    assert req_map["REQ-014"]["paused_or_closed_date"] == "2026-08-12"
    assert req_map["REQ-014"]["pipeline_count"] == 3

    assert req_map["REQ-015"]["status"] == "On hold"
    assert req_map["REQ-015"]["paused_or_closed_date"] == "2026-08-12"
    assert req_map["REQ-015"]["pipeline_count"] == 5

    # Total in pipeline for frozen roles is 8
    assert req_map["REQ-014"]["pipeline_count"] + req_map["REQ-015"]["pipeline_count"] == 8


def test_leave_register_priya_nair_half_days(test_db: DatabaseManager) -> None:
    rows = test_db.query(
        """SELECT * FROM leave_records
           WHERE employee_id = 'VX007' AND leave_type LIKE '%half day%'
           ORDER BY start_date"""
    )
    assert len(rows) == 5
    dates = [r["start_date"] for r in rows]
    assert dates == ["2026-09-03", "2026-09-08", "2026-09-15", "2026-09-17", "2026-09-24"]
    assert all(r["days_count"] == 0.5 for r in rows)


def test_pulse_survey_anonymity_enforced(test_db: DatabaseManager) -> None:
    rows = test_db.query("SELECT * FROM pulse_surveys")
    assert len(rows) == 24
    # All rows must have comments_withheld = True (1 in SQLite)
    for r in rows:
        assert r["comments_withheld"] in (1, True)
        assert "anonymity" in r["withhold_reason"].lower()

    # Jul-Sep 2026 Engineering score should be 3.1
    eng_jul_sep = test_db.query(
        "SELECT * FROM pulse_surveys WHERE department = 'Engineering' AND survey_period = 'Jul-Sep 2026'"
    )
    assert len(eng_jul_sep) == 1
    assert eng_jul_sep[0]["avg_score"] == 3.1
    assert eng_jul_sep[0]["respondent_count"] == 4


def test_resignation_letter_document(test_db: DatabaseManager) -> None:
    doc = test_db.query("SELECT * FROM documents WHERE doc_id = 'DOC_RESIGNATION_SM'")
    assert len(doc) == 1
    content = doc[0]["content_text"]
    assert "Siddharth Mehta" in content
    assert "31 October 2026" in content
    assert "launch timelines" in content


def test_point_in_time_isolation(test_db: DatabaseManager) -> None:
    # Querying Day 1 (2026-11-16) must return ZERO Day 2 evidence rows
    day1_ev = test_db.query(
        "SELECT evidence_id FROM evidence_index WHERE release_date <= ? AND evidence_id >= 'E022'",
        ("2026-11-16",),
    )
    assert len(day1_ev) == 0

    # Querying Day 2 (2026-11-17) returns all Day 2 evidence rows
    day2_ev = test_db.query(
        "SELECT evidence_id FROM evidence_index WHERE release_date <= ?",
        ("2026-11-17",),
    )
    assert len(day2_ev) >= 35


def test_ranked_risk_engine_day1_vs_day2(test_db: DatabaseManager) -> None:
    # 1. Day 1 worries (as of 2026-11-16)
    w_day1 = get_ranked_worries(db=test_db, as_of_date="2026-11-16", top_n=3)
    assert w_day1["as_of_date"] == "2026-11-16"
    assert len(w_day1["top_worries"]) == 3
    # Check that no Day 2 evidence is cited in Day 1 worries
    for w in w_day1["top_worries"]:
        for eid in w["evidence_ids"]:
            assert eid < "E022"

    # 2. Day 2 worries (as of 2026-11-17)
    w_day2 = get_ranked_worries(db=test_db, as_of_date="2026-11-17", top_n=3)
    assert w_day2["as_of_date"] == "2026-11-17"
    assert len(w_day2["top_worries"]) == 3
    top1 = w_day2["top_worries"][0]
    top2 = w_day2["top_worries"][1]
    top3 = w_day2["top_worries"][2]

    # Verify Top 3 titles match the key strategic fires
    assert "Atlas v3 Delivery & Capacity Crisis" in top1["title"]
    assert top1["severity"] == "Critical"
    assert "E023" in top1["evidence_ids"]

    assert "Engineering Morale Collapse" in top2["title"]
    assert top2["severity"] == "High"
    assert "E029" in top2["evidence_ids"]
    assert "E026" in top2["evidence_ids"]

    assert "Product Marketing Departure" in top3["title"]
    assert "E031" in top3["evidence_ids"]

    # Verify that requesting top_n=None returns the full set (> 3)
    all_w = get_ranked_worries(db=test_db, as_of_date="2026-11-17", top_n=None)
    assert len(all_w["top_worries"]) == 5
    assert len(all_w["all_worries"]) == 5


def test_voice_note_t6a_decision(test_db: DatabaseManager) -> None:
    vn = test_db.query("SELECT * FROM voice_note_decisions WHERE note_id = 'T6a'")
    assert len(vn) == 1
    assert vn[0]["decision_type"] == "implemented"
    assert Path(vn[0]["doc_path"]).is_file()


def test_sqlite_postgres_parity(test_db: DatabaseManager) -> None:
    if not test_db.postgres_enabled:
        pytest.skip("DATABASE_URL not set; skipping Supabase parity check")

    sqlite_counts = test_db.table_counts(use_postgres=False)
    postgres_counts = test_db.table_counts(use_postgres=True)

    for tbl, cnt in sqlite_counts.items():
        assert postgres_counts[tbl] == cnt, f"Count mismatch for {tbl}: sqlite={cnt}, pg={postgres_counts[tbl]}"
