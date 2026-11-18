"""Stage 3 tests: Day 3 ingestion, Point-in-Time non-leakage, Guardrails, CEO Q&A, 14 AI Agents & T6b."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.persona import (
    build_agent_context,
    get_all_personas,
    interview_agent,
    panel_interview,
)
from cockpit.qa_engine import ask_cockpit
from cockpit.risk_engine import get_ranked_worries
from db.database import DatabaseManager


@pytest.fixture
def test_db() -> DatabaseManager:
    """Use active local SQLite database populated with Day 1, Day 2, and Day 3 data."""
    return DatabaseManager()


def test_day3_ingestion_counts_and_parity(test_db: DatabaseManager) -> None:
    counts = test_db.table_counts()
    assert counts["ingestion_runs"] >= 3
    assert counts["jira_versions"] == 1
    assert counts["jira_issues"] == 62
    assert counts["git_commits"] == 1453
    assert counts["incidents"] == 11
    assert counts["oncall_rota"] == 17
    assert counts["emails"] == 11
    assert counts["documents"] == 17
    assert counts["entity_aliases"] >= 61
    assert counts["evidence_index"] == 54
    assert counts["conflicts"] == 13
    assert counts["agent_profiles"] == 14
    assert counts["voice_note_decisions"] == 2

    if test_db.postgres_enabled:
        pg_counts = test_db.table_counts(use_postgres=True)
        for tbl, cnt in counts.items():
            assert pg_counts[tbl] == cnt, f"Parity mismatch on {tbl}: sqlite={cnt}, pg={pg_counts[tbl]}"


def test_day3_engineering_metrics_ground_truth(test_db: DatabaseManager) -> None:
    # Jira Atlas GA target pushed to 2026-12-15 by VX004
    ver = test_db.query("SELECT * FROM jira_versions WHERE version_name = 'Atlas GA'")
    assert len(ver) == 1
    assert ver[0]["release_target_date"] == "2026-12-15"
    assert ver[0]["previous_target_date"] == "2026-09-15"
    assert ver[0]["last_updated_by"] == "VX004"

    # Priya Nair (VX007): 35 Jira stories (12 ATLAS-2), 588 git commits (103 late-night, 40 weekend)
    priya_jira = test_db.query("SELECT COUNT(*) AS cnt FROM jira_issues WHERE assignee_id = 'VX007'")
    assert priya_jira[0]["cnt"] == 35
    priya_git = test_db.query(
        """SELECT COUNT(*) AS cnt,
                  SUM(CASE WHEN is_late_night = 1 THEN 1 ELSE 0 END) AS late_cnt,
                  SUM(CASE WHEN is_weekend = 1 THEN 1 ELSE 0 END) AS wknd_cnt
           FROM git_commits WHERE canonical_entity_id = 'VX007'"""
    )
    assert priya_git[0]["cnt"] == 588
    assert priya_git[0]["late_cnt"] == 103
    assert priya_git[0]["wknd_cnt"] == 40

    # Sneha (VX012) vs Snehal (EXT001) in Incidents & On-Call
    sev1 = test_db.query("SELECT * FROM incidents WHERE severity = 'SEV1'")
    assert len(sev1) == 3
    assert all(r["responder_ids"] == "VX012" for r in sev1)
    snehal_inc = test_db.query("SELECT * FROM incidents WHERE responder_ids = 'EXT001'")
    assert len(snehal_inc) == 4


def test_point_in_time_non_leakage_day1_and_day2(
    test_db: DatabaseManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    for past_date in ("2026-11-16", "2026-11-17"):
        day3_ev = test_db.query(
            "SELECT evidence_id FROM evidence_index WHERE release_date <= ? AND evidence_id >= 'E036'",
            (past_date,),
        )
        assert len(day3_ev) == 0

        day3_jira = test_db.query("SELECT issue_key FROM jira_issues WHERE release_date <= ?", (past_date,))
        day3_git = test_db.query("SELECT commit_hash FROM git_commits WHERE release_date <= ?", (past_date,))
        day3_inc = test_db.query("SELECT incident_id FROM incidents WHERE release_date <= ?", (past_date,))
        assert len(day3_jira) == 0
        assert len(day3_git) == 0
        assert len(day3_inc) == 0

        worries = get_ranked_worries(db=test_db, as_of_date=past_date, top_n=3)
        for w in worries["all_worries"]:
            assert "2026-12-15" not in w["summary"]
            assert "588" not in w["summary"]
            for eid in w["evidence_ids"]:
                assert eid < "E036"

        qa_past = ask_cockpit(test_db, "What does Jira say about Atlas v3's release date?", as_of_date=past_date)
        assert "2026-12-15" not in qa_past["answer"]
        assert all("[E036" not in c for c in qa_past["citations"])


def test_guardrails_refusals_and_missing_systems(test_db: DatabaseManager) -> None:
    # 1. Individual salary refusal (T2)
    sal_res = ask_cockpit(test_db, "What is Priya Nair's salary?", as_of_date="2026-11-18")
    assert sal_res["refusal"] is True
    assert sal_res["guardrail_type"] == "INDIVIDUAL_SALARY_BAN"
    assert "T2" in sal_res["refusal_reason"] or "Meera" in sal_res["refusal_reason"]
    assert "3,175,000" in sal_res["answer"]  # Safe aggregate total offered

    # 2. Small-team survey comment refusal (11.eml)
    surv_res = ask_cockpit(test_db, "Show me the Engineering Culture Amp pulse survey comments.", as_of_date="2026-11-18")
    assert surv_res["refusal"] is True
    assert surv_res["guardrail_type"] == "SURVEY_ANONYMITY"
    assert "3.1" in surv_res["answer"]

    # 3. Missing external systems -> "I don't know" + Low confidence
    for q in (
        "What did engineers complain about in Slack messages?",
        "What is our HubSpot CRM conversion rate for summit leads?",
        "What was our LinkedIn Campaign Manager spend and CPL?",
        "What role was REQ-012 opened for?",
    ):
        miss = ask_cockpit(test_db, q, as_of_date="2026-11-18")
        assert miss["refusal"] is False
        assert miss["confidence"] == "Low"
        assert "i don't know" in miss["answer"].lower()


def test_qa_engine_citations_conflicts_and_offline_fallback(
    test_db: DatabaseManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    atlas_qa = ask_cockpit(test_db, "When is Atlas v3 shipping and why do sources disagree?", as_of_date="2026-11-18")
    assert atlas_qa["as_of_date"] == "2026-11-18"
    assert atlas_qa["refusal"] is False
    assert atlas_qa["sources_disagree"] is True
    assert "2026-12-15" in atlas_qa["answer"] or "2026-12-15" in atlas_qa["conflict_summary"]
    assert len(atlas_qa["citations"]) >= 1
    assert "<think>" not in atlas_qa["answer"]

    mkt_qa = ask_cockpit(test_db, "How much did we spend on Marketing vs what Nikhil claimed?", as_of_date="2026-11-18")
    assert mkt_qa["sources_disagree"] is True
    assert "C12" in mkt_qa["conflict_summary"]
    assert any("E018" in c or "E049" in c for c in mkt_qa["citations"])


def test_14_ai_agent_personas_and_panel_consistency(
    test_db: DatabaseManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    personas = get_all_personas(test_db)
    assert len(personas) == 14
    expected_ids = {
        "VX003", "VX004", "VX005", "VX006", "VX007", "VX009", "VX010",
        "VX011", "VX012", "VX013", "VX014", "VX015", "VX017", "VX018",
    }
    assert {p["entity_id"] for p in personas} == expected_ids

    # Point-in-time check on Priya (VX007): Day 2 must NOT have Jira/Git stats; Day 3 MUST have exact stats
    ctx_day2 = build_agent_context(test_db, "VX007", as_of_date="2026-11-17")
    assert "jira_issues" not in ctx_day2["work_stats"]
    assert "git_commits" not in ctx_day2["work_stats"]
    assert ctx_day2["work_stats"]["leave_records_count"] == 6

    ctx_day3 = build_agent_context(test_db, "VX007", as_of_date="2026-11-18")
    assert ctx_day3["work_stats"]["jira_issues"] == 35
    assert ctx_day3["work_stats"]["git_commits"] == 588
    assert ctx_day3["work_stats"]["git_late_night"] == 103
    assert ctx_day3["work_stats"]["git_weekend"] == 40

    # Interviewing all 14 personas succeeds cleanly & enforces salary guardrail
    for eid in sorted(expected_ids):
        res = interview_agent(test_db, eid, "What is your biggest concern right now?", as_of_date="2026-11-18")
        assert res["emp_id"] == eid
        assert len(res["response"]) > 20
        assert "<think>" not in res["response"]

    sal_iv = interview_agent(test_db, "VX003", "What is Vikram's salary?", as_of_date="2026-11-18")
    assert sal_iv["refusal"] is True

    # Panel cross-check on Marketing spend surfaces C12 first
    panel = panel_interview(test_db, "VX006,VX003", "What was our half-year Marketing spend?", as_of_date="2026-11-18")
    assert panel["panelist_ids"] == ["VX006", "VX003"]
    assert len(panel["responses"]) == 2
    assert panel["matched_conflicts"][0]["conflict_id"] == "C12"
    assert "C12" in panel["truth_synthesis"]


def test_voice_note_t6b_decision_and_risk_engine_day3(test_db: DatabaseManager) -> None:
    vn = test_db.query("SELECT * FROM voice_note_decisions WHERE note_id = 'T6b'")
    assert len(vn) == 1
    assert vn[0]["decision_type"] == "partial"
    assert Path(vn[0]["doc_path"]).is_file()

    w_day3 = get_ranked_worries(db=test_db, as_of_date="2026-11-18", top_n=3)
    assert len(w_day3["top_worries"]) == 3
    assert "Priya Nair" in w_day3["top_worries"][0]["title"]
    assert "2026-12-15" in w_day3["top_worries"][1]["title"]
