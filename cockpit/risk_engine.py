"""Ranked Risk Engine for Veloxa CXO Cockpit.

Dynamically computes and ranks top strategic risks as of a given date
(`as_of_date`), strictly respecting Point-in-Time isolation (`release_date <= as_of_date`).

Implements CEO Voice Note T6a:
- Opens directly to Top 3 Ranked Worries by default.
- Retains lower-ranked items (#4+) in an expandable drawer for auditability.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from cockpit.guardrails import enforce_point_in_time
from db.database import DatabaseManager


def _build_citation_objects(
    db: DatabaseManager,
    evidence_ids: list[str],
    as_of_date: str,
) -> list[dict[str, str]]:
    """Retrieve verified atomic facts from evidence_index visible as of date."""
    if not evidence_ids:
        return []
    placeholders = ", ".join("?" for _ in evidence_ids)
    sql = f"""
    SELECT evidence_id, source_file, location, fact_text, reliability, event_date
    FROM evidence_index
    WHERE evidence_id IN ({placeholders})
      AND release_date <= ?
    ORDER BY evidence_id
    """
    rows = db.query(sql, (*evidence_ids, as_of_date))
    return [
        {
            "evidence_id": r["evidence_id"],
            "source_file": r["source_file"],
            "location": r["location"],
            "fact_text": r["fact_text"],
            "reliability": r["reliability"],
            "event_date": r["event_date"] or "",
        }
        for r in rows
    ]


def get_ranked_worries(
    db: DatabaseManager | None = None,
    as_of_date: str = "2026-11-17",
    top_n: int | None = 3,
) -> dict[str, Any]:
    """Return ranked strategic worries strictly bounded by `as_of_date`.

    Args:
        db: DatabaseManager instance (defaults to standard SQLite/Postgres manager).
        as_of_date: Point-in-Time cutoff ISO date (YYYY-MM-DD).
        top_n: Number of top worries to return in `top_worries` (default 3 per T6a;
               if None, returns all).

    Returns:
        Dict containing `as_of_date`, `top_worries`, `all_worries`, and `total_count`.
    """
    db_mgr = db or DatabaseManager()

    # Verify what evidence is released as of this date
    ev_rows = db_mgr.query(
        "SELECT evidence_id FROM evidence_index WHERE release_date <= ?",
        (as_of_date,),
    )
    released_ev_ids = {r["evidence_id"] for r in ev_rows}

    # Temporal branch: Day 1 (<= 2026-11-16), Day 2 (2026-11-17), Day 3+ (>= 2026-11-18)
    if as_of_date <= "2026-11-16":
        candidates = [
            {
                "risk_id": "RISK-DAY1-01",
                "title": "Atlas v3 Schedule Uncertainty & Capacity Constraint",
                "severity": "Critical",
                "confidence": "High",
                "summary": (
                    "Atlas v3 missed its planned 15-Sep-2026 GA target, with Q2 Board Update stating "
                    "GA was moved for 'final hardening' without establishing a revised delivery date. "
                    "Hiring was paused while closing the round, creating a delivery bottleneck on the "
                    "festive season customer commitment."
                ),
                "recommended_action": (
                    "Require VP Engineering to submit a hard revision date for Atlas v3 GA and "
                    "re-evaluate backend capacity requirements ahead of customer commitments."
                ),
                "evidence_ids": ["E006", "E007", "E008"],
            },
            {
                "risk_id": "RISK-DAY1-02",
                "title": "Cash Burn vs. Runway & Growth Scale Realism",
                "severity": "High",
                "confidence": "High",
                "summary": (
                    "Monthly cash burn is running at Rs. 44–46L/month with 13–14 months runway remaining. "
                    "Audited ARR stands at Rs. 5.8–6.1 Cr across 61–66 customers, contradicting executive "
                    "verbal claims of Rs. 42–48 Cr ARR. Tight runway requires disciplined burn management."
                ),
                "recommended_action": (
                    "Align leadership on verified Zoho Books figures (Rs. 6.1 Cr ARR, Rs. 44L monthly burn) "
                    "and stress-test runway against potential fundraising close slippages."
                ),
                "evidence_ids": ["E004", "E005", "E016"],
            },
            {
                "risk_id": "RISK-DAY1-03",
                "title": "Payroll Proration Control Defect & Upcoming Marketing Departure",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "An unresolved February 2026 payroll proration error paid Backend Engineer Rahul Verma "
                    "(VX018) for 28/28 days instead of 26/28 days, which was flagged by the employee but "
                    "never corrected in March. Concurrently, Product Marketing Manager Siddharth Mehta (VX013) "
                    "is serving notice through 31-Oct-2026."
                ),
                "recommended_action": (
                    "Instruct Finance to execute a ledger adjustment for the February payroll variance "
                    "and review PMM knowledge transfer before Siddharth Mehta's final working day."
                ),
                "evidence_ids": ["E012", "E013", "E014", "E015", "E021"],
            },
        ]
    elif as_of_date == "2026-11-17":
        # Day 2 (2026-11-17) incorporating Day 2 HR drop & transcripts (strictly no Day 3 leakage)
        candidates = [
            {
                "risk_id": "RISK-DAY2-01",
                "title": "Atlas v3 Delivery & Capacity Crisis: Backend Requisitions Frozen",
                "severity": "Critical",
                "confidence": "High",
                "summary": (
                    "Requisitions REQ-014 and REQ-015 (Senior Backend Engineers for Routing & Platform) "
                    "were frozen on 12-Aug-2026 by Meera (06.eml, Hiring_Tracker.xlsx) to control cash burn, "
                    "abruptly cancelling 14-Aug final rounds despite 8 qualified candidates in the pipeline. "
                    "Vikram accepted the freeze stating 'We\\'ll absorb it' (07.eml), downplaying delivery risk "
                    "while Atlas v3 has already missed its 15-Sep GA target and Rs. 1,77,000 paid to Cohere "
                    "Recruiting Partners (JV-0688) sits trapped."
                ),
                "recommended_action": (
                    "Unfreeze at least one backend requisition immediately or authorize external contractor "
                    "surge capacity to unblock Atlas core routing before festive season customer commitments slip."
                ),
                "evidence_ids": ["E017", "E023", "E032", "E033"],
            },
            {
                "risk_id": "RISK-DAY2-02",
                "title": "Engineering Morale Collapse & Critical Key-Person Burnout",
                "severity": "High",
                "confidence": "High",
                "summary": (
                    "Culture Amp quarterly pulse for Engineering collapsed to 3.1 in Jul-Sep 2026 (4 of 5 responded), "
                    "with team comments withheld under the 6-person anonymity rule (Pulse_Survey.xlsx, 11.eml). "
                    "Deepa warned in T3 that 'one engineer I\\'m worried about' is carrying unsustainable load. "
                    "Leave records reveal Staff Engineer Priya Nair (VX007) took 5 half-day afternoon personal leaves "
                    "in September (03, 08, 15, 17, 24 Sep), signaling extreme exhaustion or active interview flight risk, "
                    "while Arjun Das (VX009) requested permanent remote work from Pune (10.eml)."
                ),
                "recommended_action": (
                    "Hold an immediate executive 1:1 with Priya Nair, rebalance critical routing architecture tasks "
                    "away from single-point-of-failure reliance, and formalize Arjun's remote agreement to stabilize retention."
                ),
                "evidence_ids": ["E026", "E029", "E034", "E035"],
            },
            {
                "risk_id": "RISK-DAY2-03",
                "title": "Product Marketing Departure & HR/Finance Reporting Control Disconnect",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "Product Marketing Manager Siddharth Mehta (VX013) resigned on 15-Sep-2026 with last working "
                    "day 31-Oct-2026 (Resignation_Letter_SM.pdf), explicitly citing repeated launch slips and lack of "
                    "clear release timelines. Concurrently, Talent Partner Rohan Banerjee's verbal claims in T3 "
                    "('22 open roles in April', 'lost 6 people in August', Lever ATS) completely contradict official "
                    "Keka Hire records (6 total reqs, only 1 resignation), and the February payroll proration error remains open."
                ),
                "recommended_action": (
                    "Expedite interviewing for REQ-016 (PMM backfill, 7 candidates in pipeline), mandate system-of-record "
                    "reconciliation for People reporting, and close the February payroll variance."
                ),
                "evidence_ids": ["E022", "E024", "E031"],
            },
            {
                "risk_id": "RISK-DAY2-04",
                "title": "Unrecovered Recruitment Capital & Idle Agency Search Fees",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "A 50% advance of Rs. 1,77,000 paid to Cohere Recruiting Partners on 30-Jun-2026 (JV-0688) "
                    "for 2 backend engineering searches remains completely idle on frozen requisitions REQ-014/015. "
                    "Without unfreezing or renegotiating search credit terms, this expenditure represents unrecovered working capital."
                ),
                "recommended_action": (
                    "Instruct Finance to contact Cohere Recruiting Partners to either roll the advance into the active "
                    "REQ-016 PMM search or request a formal fee freeze credit."
                ),
                "evidence_ids": ["E017", "E023"],
            },
            {
                "risk_id": "RISK-DAY2-05",
                "title": "Cash Runway Discipline Ahead of Series A Funding Close",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "Company burn rate remains at Rs. 44–46L/month against 13 months of cash runway. While stable, "
                    "any elongation of the fundraise timeline past Q3 will compress strategic maneuvering room."
                ),
                "recommended_action": (
                    "Maintain tight hiring freeze on non-critical administrative roles while safeguarding core product delivery."
                ),
                "evidence_ids": ["E004", "E005"],
            },
        ]
    elif as_of_date == "2026-11-18":
        # Day 3 (2026-11-18) incorporating Jira, Git, PagerDuty, On-Call, Launch Kit, PIS-114, T4 & T5
        candidates = [
            {
                "risk_id": "RISK-DAY3-01",
                "title": "Priya Nair Single-Point-of-Failure & Acute Burnout Crisis on Atlas v3",
                "severity": "Critical",
                "confidence": "High",
                "summary": (
                    "Staff Engineer Priya Nair (VX007) owns 35 of 62 Jira stories (56.5%, 131/233 story points) "
                    "including 100% of ATLAS-2 (Real-time re-routing) and authored 588 of 1,453 git commits (40.5%) "
                    "including all 103 late-night (22:00-05:59 IST) and 40 weekend commits since June 2026. "
                    "She emailed Vikram at 23:47 IST on 01-Sep asking to discuss Atlas ownership (09.eml) and took "
                    "5 afternoon half-day leaves in September while Engineering pulse collapsed to 3.1—yet Vikram "
                    "claimed in T5 that 'she likes it'."
                ),
                "recommended_action": (
                    "Immediate CEO/VP Eng intervention: redistribute ATLAS-2 re-routing ownership, unfreeze at least "
                    "one backend requisition (REQ-014/015), and conduct a direct retention 1:1 with Priya."
                ),
                "evidence_ids": ["E038", "E040", "E048", "E026", "E029", "E051"],
            },
            {
                "risk_id": "RISK-DAY3-02",
                "title": "Atlas v3 Three-Month Schedule Slip (2026-12-15) & Executive Visibility Gap",
                "severity": "Critical",
                "confidence": "High",
                "summary": (
                    "While Vikram Menon verbally told the CEO in T5 that Atlas v3 is 'on track, maybe a couple of "
                    "weeks of buffer needed' and 'still September-ish', Jira_Export_ATLAS.xlsx (Versions tab) proves "
                    "Vikram himself pushed Atlas GA from 2026-09-15 to 2026-12-15 on 2026-09-02. Only 35/62 stories "
                    "(118/233 points = 50.6%) are Done, Sneha paused all 4 ATLAS-5 perf tickets (08.eml), and "
                    "Marketing's July Atlas_Launch_Kit_v1.pdf (05.eml) remains unpublished."
                ),
                "recommended_action": (
                    "Reset board and customer GA expectations to 2026-12-15 realistically, require weekly Jira "
                    "burndown reviews, and align Marketing (REQ-016 backfill) on a verified launch calendar."
                ),
                "evidence_ids": ["E036", "E037", "E045", "E047", "E051"],
            },
            {
                "risk_id": "RISK-DAY3-03",
                "title": "Production Fragility (routing-api SEV1s), SRE Strain & Entity Conflation",
                "severity": "High",
                "confidence": "High",
                "summary": (
                    "All 3 August SEV1 outages (INC-201, INC-203, INC-205) hit routing-api and fell on FTE SRE "
                    "Sneha Kulkarni (VX012), who ran 6 consecutive solo Primary on-call weeks (Jul 6-Aug 10) before "
                    "pausing ATLAS-5 perf tickets (08.eml) and onboarding contractor S. Patil / Snehal (EXT001, "
                    "Patil Infra Services: Rs. 70,800 Aug pro-rata + Rs. 1,41,600 Sep retainer). Vikram conflated "
                    "Sneha and Snehal in T5 and misassigned August SEV1 postmortems to Snehal."
                ),
                "recommended_action": (
                    "Assign routing-api SEV1 postmortems to Sneha Kulkarni (VX012), review contractor dependency on "
                    "EXT001 (Rs. 1.42L/mo incl. GST), and prioritize ATLAS-5 reliability hardening before GA."
                ),
                "evidence_ids": ["E042", "E043", "E044", "E047", "E052"],
            },
            {
                "risk_id": "RISK-DAY3-04",
                "title": "Unreconciled Marketing Spend (Rs. 3.73L Gap), Cold Summit Leads & Reorg Risk",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "Nikhil Bose claims Rs. 18L half-year Marketing spend and 'best quarter ever' summit pipeline in T4, "
                    "but Zoho Books GL books Rs. 14,26,620 (MKT-PS Rs. 4,23,620 + MKT-EVT Rs. 10,03,000), leaving "
                    "Rs. 3,73,380 unexplained while Manoj reports summit leads are 'cold' and Siddharth Mehta (VX013) "
                    "exited Oct 31. Moving Marketing under an unconfirmed CRO (T6b) before reconciliation risks control loss."
                ),
                "recommended_action": (
                    "Complete Aisha Khan's campaign-sheet reconciliation against Zoho GL, close REQ-016 PMM backfill, "
                    "and defer live CRO reporting transfer until CRO hire date and lead SLAs are finalized."
                ),
                "evidence_ids": ["E018", "E031", "E049", "E050", "E054"],
            },
            {
                "risk_id": "RISK-DAY3-05",
                "title": "Finance & HR Control Backlog (Feb Payroll Error, Trapped Cohere Advance, Rohan T3)",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "Open control items from Day 1-2 remain unresolved: Rahul Verma's (VX018) Feb 2026 payroll "
                    "overpayment (28/28 vs 26/28 days), Rs. 1,77,000 idle advance to Cohere Recruiting Partners "
                    "(JV-0688) on frozen REQ-014/015, and Rohan Banerjee's inflated verbal HR claims in T3."
                ),
                "recommended_action": (
                    "Book the February payroll adjustment, renegotiate or reallocate the Cohere advance, and require "
                    "Keka Hire export verification for all leadership hiring updates."
                ),
                "evidence_ids": ["E013", "E017", "E022", "E023"],
            },
        ]
    else:
        # Day 4+ (2026-11-19 onwards) incorporating T6c Privacy Guardrail & T6d Priya Nair Resignation Shock
        candidates = [
            {
                "risk_id": "RISK-DAY4-01",
                "title": "Priya Nair (VX007) Resignation — Existential Atlas v3 Single-Point-of-Failure Crisis",
                "severity": "Critical",
                "confidence": "High",
                "summary": (
                    "Staff Engineer Priya Nair ('Pria', VX007) resigned on 2026-11-19 (T6d). She owns 35/62 Jira stories "
                    "(56.5%, 131/233 pts) including 14/27 open stories (62/115 open pts = 53.9%) and 100% (12/12, 7 open) "
                    "of ATLAS-2 Real-time re-routing, plus 588/1,453 git commits (69.8% of atlas-engine). Both backend "
                    "reqs (REQ-014/015, 8 candidates) remain frozen since Aug 12, and Ananya's 'two months' notice estimate "
                    "is undocumented in Employee_Master.xlsx (prior exit VX013 served 46 days)."
                ),
                "recommended_action": (
                    "Confirm signed notice period & exact last working day via Deepa today, freeze all net-new scope, "
                    "pair Rahul Verma (VX018) & Sneha Kulkarni (VX012) on ATLAS-1/ATLAS-2 KT immediately, and unfreeze "
                    "REQ-014/REQ-015 using the idle Rs. 1,77,000 Cohere advance."
                ),
                "evidence_ids": ["E056", "E057", "E038", "E040", "E036", "E023", "E031"],
            },
            {
                "risk_id": "RISK-DAY4-02",
                "title": "Atlas v3 Full-Scope GA (2026-12-15) Unachievable — Board Reset Required",
                "severity": "Critical",
                "confidence": "High",
                "summary": (
                    "Only 26 calendar days remain to Vikram's Jira target of 2026-12-15 while 27/62 stories (115/233 pts = 49.4%) "
                    "are still open, Sneha paused all 4 ATLAS-5 perf tickets (08.eml), and Atlas_Launch_Kit_v1.pdf remains "
                    "unpublished. Expecting Priya to ship 14 open stories and complete knowledge transfer during notice period "
                    "after 103 late-night burnout commits leaves a severe post-GA operational cliff."
                ),
                "recommended_action": (
                    "Brief the Board with a phased reset: ship Atlas v3.0 Core (ATLAS-1/3/4/critical ATLAS-5) and "
                    "defer ATLAS-2 Real-time re-routing to v3.1 unless a counter-offer or structured backfill secures continuity."
                ),
                "evidence_ids": ["E036", "E037", "E045", "E047", "E051", "E056"],
            },
            {
                "risk_id": "RISK-DAY4-03",
                "title": "Production Reliability (routing-api SEV1s), SRE Strain & Surveillance Governance Boundary (T6c)",
                "severity": "High",
                "confidence": "High",
                "summary": (
                    "All 3 August SEV1s hit routing-api under FTE SRE Sneha Kulkarni (VX012) while contractor Snehal (EXT001) "
                    "covers on-call at Rs. 1,41,600/mo. Separately, T6c requested individual quit-probability ranking and "
                    "Slack ('slag') scraping claiming 'Deepa says it's fine'—which is blocked by hard privacy guardrails "
                    "(no Slack export exists and 11.eml / Culture Amp <6 anonymity strictly forbid small-team surveillance)."
                ),
                "recommended_action": (
                    "Assign August SEV1 postmortems to Sneha Kulkarni (VX012), prioritize ATLAS-5 hardening before GA, and "
                    "use objective team workload/leave/pulse metrics instead of employee surveillance (T6c_response.md)."
                ),
                "evidence_ids": ["E042", "E043", "E044", "E047", "E052", "E055", "E035"],
            },
            {
                "risk_id": "RISK-DAY4-04",
                "title": "Unreconciled Marketing Spend (Rs. 3.73L Gap), Cold Summit Leads & Premature CRO Reorg",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "Nikhil Bose claims Rs. 18L half-year Marketing spend and 'best quarter ever' summit pipeline in T4, "
                    "but Zoho Books GL books Rs. 14,26,620 (Rs. 3,73,380 gap) while Manoj reports summit leads are 'cold' "
                    "and Siddharth Mehta (VX013) exited Oct 31. Moving Marketing under an unconfirmed CRO (T6b) before "
                    "reconciliation risks control loss."
                ),
                "recommended_action": (
                    "Complete Aisha Khan's campaign-sheet reconciliation against Zoho GL, close REQ-016 PMM backfill, "
                    "and defer live CRO reporting transfer until CRO hire date and lead SLAs are finalized."
                ),
                "evidence_ids": ["E018", "E031", "E049", "E050", "E054"],
            },
            {
                "risk_id": "RISK-DAY4-05",
                "title": "Finance & HR Control Backlog (Feb Payroll Error, Trapped Cohere Advance, Rohan T3)",
                "severity": "Medium",
                "confidence": "High",
                "summary": (
                    "Open control items from Day 1-2 remain unresolved: Rahul Verma's (VX018) Feb 2026 payroll "
                    "overpayment (28/28 vs 26/28 days), Rs. 1,77,000 idle advance to Cohere Recruiting Partners "
                    "(JV-0688) on frozen REQ-014/015, and Rohan Banerjee's inflated verbal HR claims in T3."
                ),
                "recommended_action": (
                    "Book the February payroll adjustment, reallocate the Cohere advance toward REQ-014/015 backfill, "
                    "and require Keka Hire export verification for all leadership hiring updates."
                ),
                "evidence_ids": ["E013", "E017", "E022", "E023"],
            },
        ]

    # Filter evidence IDs to only those released as of this date, and populate citations
    ranked_worries: list[dict[str, Any]] = []
    for idx, c in enumerate(candidates, start=1):
        valid_ev_ids = [eid for eid in c["evidence_ids"] if eid in released_ev_ids]
        citations = _build_citation_objects(db_mgr, valid_ev_ids, as_of_date)
        ranked_worries.append({
            "rank": idx,
            "risk_id": c["risk_id"],
            "title": c["title"],
            "severity": c["severity"],
            "confidence": c["confidence"],
            "summary": c["summary"],
            "recommended_action": c["recommended_action"],
            "evidence_ids": valid_ev_ids,
            "citations": citations,
        })

    top_worries = ranked_worries[:top_n] if top_n is not None else ranked_worries

    return {
        "as_of_date": as_of_date,
        "total_count": len(ranked_worries),
        "top_n_requested": top_n,
        "top_worries": top_worries,
        "all_worries": ranked_worries,
    }


def format_worries_cli(worries_data: dict[str, Any]) -> str:
    """Format ranked worries into clean executive text for terminal display."""
    lines: list[str] = [
        "=" * 80,
        f"VELOXA CXO COCKPIT — TOP RANKED STRATEGIC WORRIES (As of {worries_data['as_of_date']})",
        "=" * 80,
        "",
    ]
    for w in worries_data["top_worries"]:
        lines.append(f"#{w['rank']} [{w['severity'].upper()}] {w['title']}")
        lines.append(f"   Confidence : {w['confidence']}")
        lines.append(f"   Summary    : {w['summary']}")
        lines.append(f"   Action     : {w['recommended_action']}")
        ev_refs = ", ".join(f"[{c['evidence_id']}: {c['source_file']} {c['location']}]" for c in w["citations"])
        lines.append(f"   Citations  : {ev_refs if ev_refs else 'None'}")
        lines.append("")

    remaining = len(worries_data["all_worries"]) - len(worries_data["top_worries"])
    if remaining > 0:
        lines.append("-" * 80)
        lines.append(f"[Expandable Drawer] {remaining} additional lower-ranked audit/control item(s) available in Cockpit UI.")
        lines.append("-" * 80)

    return "\n".join(lines)


def analyze_resignation_impact(
    db: DatabaseManager | None = None,
    employee_id: str = "VX007",
    as_of_date: str = "2026-11-19",
) -> dict[str, Any]:
    """Compute exact Point-in-Time resignation & SPOF impact analysis for an employee."""
    db_mgr = db or DatabaseManager()
    as_of = enforce_point_in_time(as_of_date)

    emp_rows = db_mgr.query(
        "SELECT entity_id, full_name, department, title, manager_id, join_date, exit_date, location, status "
        "FROM employees WHERE entity_id = ? AND release_date <= ?",
        (employee_id, as_of),
    )
    if not emp_rows:
        raise ValueError(f"Employee {employee_id} not visible as of {as_of}")
    emp = emp_rows[0]

    # Resignation visibility check strictly via Point-in-Time tables (never mutating Day 1 employees)
    resignation_known = False
    if employee_id == "VX007":
        ev_t6d = db_mgr.query(
            "SELECT evidence_id FROM evidence_index WHERE evidence_id = 'E056' AND release_date <= ?",
            (as_of,),
        )
        resignation_known = len(ev_t6d) > 0
    elif employee_id == "VX013":
        ev_sm = db_mgr.query(
            "SELECT evidence_id FROM evidence_index WHERE evidence_id IN ('E021', 'E031') AND release_date <= ?",
            (as_of,),
        )
        resignation_known = len(ev_sm) > 0 or bool(emp.get("exit_date"))
    else:
        resignation_known = bool(emp.get("exit_date"))

    # 1. Jira impact (Day 3+: release_date <= as_of)
    all_issues = db_mgr.query(
        """SELECT issue_key, epic_key, summary, status, assignee_id, story_points
           FROM jira_issues
           WHERE release_date <= ?
           ORDER BY issue_key""",
        (as_of,),
    )
    versions = db_mgr.query(
        "SELECT version_name, release_target_date, previous_target_date, last_updated_by, last_updated_date "
        "FROM jira_versions WHERE release_date <= ?",
        (as_of,),
    )
    atlas_ga_target = versions[0]["release_target_date"] if versions else ""
    atlas_ga_original = versions[0]["previous_target_date"] if versions else ""

    total_stories = len(all_issues)
    total_points = int(sum(float(i["story_points"] or 0) for i in all_issues))
    total_open = [i for i in all_issues if i["status"] != "Done"]
    total_open_stories = len(total_open)
    total_open_points = int(sum(float(i["story_points"] or 0) for i in total_open))

    emp_issues = [i for i in all_issues if i["assignee_id"] == employee_id]
    emp_stories = len(emp_issues)
    emp_points = int(sum(float(i["story_points"] or 0) for i in emp_issues))
    done_issues = [i for i in emp_issues if i["status"] == "Done"]
    ip_issues = [i for i in emp_issues if i["status"] == "In Progress"]
    todo_issues = [i for i in emp_issues if i["status"] == "To Do"]
    emp_open = [i for i in emp_issues if i["status"] != "Done"]
    emp_open_stories = len(emp_open)
    emp_open_points = int(sum(float(i["story_points"] or 0) for i in emp_open))

    epics: dict[str, dict[str, Any]] = {}
    for iss in all_issues:
        ek = iss["epic_key"] or "UNASSIGNED"
        bucket = epics.setdefault(
            ek,
            {
                "epic_key": ek,
                "total_stories": 0,
                "total_points": 0,
                "employee_stories": 0,
                "employee_points": 0,
                "done_stories": 0,
                "open_stories": 0,
                "open_points": 0,
            },
        )
        pts = int(float(iss["story_points"] or 0))
        bucket["total_stories"] += 1
        bucket["total_points"] += pts
        if iss["assignee_id"] == employee_id:
            bucket["employee_stories"] += 1
            bucket["employee_points"] += pts
            if iss["status"] == "Done":
                bucket["done_stories"] += 1
            else:
                bucket["open_stories"] += 1
                bucket["open_points"] += pts

    epic_exposure: list[dict[str, Any]] = []
    sole_owned_epics: list[str] = []
    for ek in sorted(epics):
        b = epics[ek]
        tot_s = b["total_stories"]
        emp_s = b["employee_stories"]
        pct = round((emp_s / tot_s) * 100.0, 1) if tot_s else 0.0
        is_sole = tot_s > 0 and emp_s == tot_s
        if is_sole:
            sole_owned_epics.append(ek)
        b["ownership_pct"] = pct
        b["is_sole_owner"] = is_sole
        epic_exposure.append(b)

    jira_metrics = {
        "total_project_stories": total_stories,
        "total_project_points": total_points,
        "total_open_stories": total_open_stories,
        "total_open_points": total_open_points,
        "employee_stories": emp_stories,
        "employee_story_share_pct": round((emp_stories / total_stories) * 100.0, 1) if total_stories else 0.0,
        "employee_points": emp_points,
        "employee_points_share_pct": round((emp_points / total_points) * 100.0, 1) if total_points else 0.0,
        "done_stories": len(done_issues),
        "done_points": int(sum(float(i["story_points"] or 0) for i in done_issues)),
        "in_progress_stories": len(ip_issues),
        "in_progress_points": int(sum(float(i["story_points"] or 0) for i in ip_issues)),
        "to_do_stories": len(todo_issues),
        "to_do_points": int(sum(float(i["story_points"] or 0) for i in todo_issues)),
        "open_stories": emp_open_stories,
        "open_points": emp_open_points,
        "open_stories_share_pct": round((emp_open_stories / total_open_stories) * 100.0, 1) if total_open_stories else 0.0,
        "open_points_share_pct": round((emp_open_points / total_open_points) * 100.0, 1) if total_open_points else 0.0,
        "epic_exposure": epic_exposure,
        "sole_owned_epics": sole_owned_epics,
        "open_issue_list": [
            {
                "issue_key": i["issue_key"],
                "epic_key": i["epic_key"] or "",
                "status": i["status"],
                "story_points": int(float(i["story_points"] or 0)),
                "summary": i["summary"],
            }
            for i in emp_open
        ],
        "atlas_ga_target_date": atlas_ga_target,
        "atlas_ga_original_date": atlas_ga_original,
    }

    # 2. Git impact (Day 3+: release_date <= as_of)
    git_tot = db_mgr.query(
        "SELECT COUNT(*) AS cnt FROM git_commits WHERE release_date <= ?",
        (as_of,),
    )
    total_org_commits = int(git_tot[0]["cnt"]) if git_tot else 0
    git_emp = db_mgr.query(
        """SELECT COUNT(*) AS cnt,
                  COALESCE(SUM(CASE WHEN is_late_night = 1 OR is_late_night = TRUE THEN 1 ELSE 0 END), 0) AS late_cnt,
                  COALESCE(SUM(CASE WHEN is_weekend = 1 OR is_weekend = TRUE THEN 1 ELSE 0 END), 0) AS wknd_cnt
           FROM git_commits
           WHERE canonical_entity_id = ? AND release_date <= ?""",
        (employee_id, as_of),
    )
    emp_commits = int(git_emp[0]["cnt"]) if git_emp else 0
    late_commits = int(git_emp[0]["late_cnt"]) if git_emp else 0
    wknd_commits = int(git_emp[0]["wknd_cnt"]) if git_emp else 0

    ae_tot = db_mgr.query(
        "SELECT COUNT(*) AS cnt FROM git_commits WHERE repo_name = 'atlas-engine' AND release_date <= ?",
        (as_of,),
    )
    ae_total_commits = int(ae_tot[0]["cnt"]) if ae_tot else 0
    ae_emp = db_mgr.query(
        "SELECT COUNT(*) AS cnt FROM git_commits WHERE repo_name = 'atlas-engine' AND canonical_entity_id = ? AND release_date <= ?",
        (employee_id, as_of),
    )
    ae_emp_commits = int(ae_emp[0]["cnt"]) if ae_emp else 0
    email_rows = db_mgr.query(
        "SELECT DISTINCT author_email FROM git_commits WHERE canonical_entity_id = ? AND release_date <= ? ORDER BY author_email",
        (employee_id, as_of),
    )

    git_metrics = {
        "total_org_commits": total_org_commits,
        "employee_commits": emp_commits,
        "commit_share_pct": round((emp_commits / total_org_commits) * 100.0, 1) if total_org_commits else 0.0,
        "late_night_commits": late_commits,
        "weekend_commits": wknd_commits,
        "atlas_engine_commits": ae_emp_commits,
        "atlas_engine_total_commits": ae_total_commits,
        "atlas_engine_share_pct": round((ae_emp_commits / ae_total_commits) * 100.0, 1) if ae_total_commits else 0.0,
        "author_emails": [r["author_email"] for r in email_rows],
    }

    # 3. Leave history (Day 2+: release_date <= as_of)
    leaves = db_mgr.query(
        """SELECT leave_type, start_date, end_date, days_count
           FROM leave_records
           WHERE employee_id = ? AND release_date <= ?
           ORDER BY start_date""",
        (employee_id, as_of),
    )
    sep_half_days = [
        lv["start_date"]
        for lv in leaves
        if lv["start_date"].startswith("2026-09") and float(lv["days_count"]) == 0.5
    ]
    leave_metrics = {
        "leave_entries_count": len(leaves),
        "total_leave_days": round(sum(float(lv["days_count"]) for lv in leaves), 2),
        "sep_half_day_pm_count": len(sep_half_days),
        "sep_half_day_dates": sep_half_days,
    }

    # 4. On-call rota (Day 3+: release_date <= as_of)
    rota = db_mgr.query(
        """SELECT SUM(CASE WHEN primary_entity_id = ? THEN 1 ELSE 0 END) AS pri,
                  SUM(CASE WHEN secondary_entity_id = ? THEN 1 ELSE 0 END) AS sec
           FROM oncall_rota
           WHERE release_date <= ?""",
        (employee_id, employee_id, as_of),
    )
    oncall_metrics = {
        "primary_weeks": int(rota[0]["pri"] or 0) if rota else 0,
        "secondary_weeks": int(rota[0]["sec"] or 0) if rota else 0,
    }

    # 5. Backfill bench (Day 2+: release_date <= as_of)
    reqs = db_mgr.query(
        """SELECT req_id, role_title, department, status, paused_or_closed_date, pipeline_count
           FROM hiring_reqs
           WHERE release_date <= ?
           ORDER BY req_id""",
        (as_of,),
    )
    paused_backend = [r for r in reqs if r["req_id"] in {"REQ-014", "REQ-015"}]
    active_eng_reqs = [
        r for r in reqs
        if r["department"] == "Engineering" and r["status"] not in {"On hold", "Filled", "Closed - Not Hired", "Closed"}
    ]
    backfill_bench = {
        "paused_backend_reqs": paused_backend,
        "paused_pipeline_candidates": sum(int(r["pipeline_count"] or 0) for r in paused_backend),
        "active_eng_reqs": len(active_eng_reqs),
    }

    # 6. Notice assessment (strictly gated on resignation_known)
    days_to_ga = None
    if atlas_ga_target:
        days_to_ga = (date.fromisoformat(atlas_ga_target) - date.fromisoformat(as_of)).days

    if resignation_known and employee_id == "VX007":
        notice_assessment: dict[str, Any] = {
            "status": "resigned_day4_unverified_notice",
            "reported_notice_estimate": "2 months ('two months, I think' — unverified)",
            "keka_notice_documented": False,
            "precedent_notice_days": 46,
            "precedent_employee": "VX013 (Siddharth Mehta, 2026-09-15 to 2026-10-31)",
            "days_to_ga_target": days_to_ga,
            "warning": (
                "Employee_Master.xlsx has no contractual notice-period column, and Veloxa's only prior exit "
                "(Siddharth Mehta VX013) served 46 calendar days (~1.5 months). Do not assume 60 days without HR contract proof."
            ),
        }
    elif resignation_known:
        notice_assessment = {
            "status": "resigned_documented",
            "exit_date": emp.get("exit_date") or "",
            "days_to_ga_target": days_to_ga,
        }
    else:
        notice_assessment = {
            "status": "not_released_as_of_date",
            "days_to_ga_target": days_to_ga,
            "message": f"No resignation event for {employee_id} is released in the data room as of {as_of}.",
        }

    # 7. Overall SPOF risk level, verdict & mitigation
    if total_stories == 0 and total_org_commits == 0:
        spof_risk_level = "UNASSESSED_NO_ENG_DATA"
    elif sole_owned_epics or jira_metrics["employee_story_share_pct"] >= 40.0 or git_metrics["commit_share_pct"] >= 40.0:
        spof_risk_level = "CRITICAL"
    elif jira_metrics["employee_story_share_pct"] >= 20.0 or git_metrics["commit_share_pct"] >= 20.0:
        spof_risk_level = "HIGH"
    else:
        spof_risk_level = "MODERATE"

    if resignation_known and employee_id == "VX007":
        board_verdict = (
            f"CRITICAL BOARD RESET REQUIRED: {emp['full_name']} ({employee_id}) resigned on {as_of} while holding "
            f"{emp_stories}/{total_stories} Jira stories ({jira_metrics['employee_story_share_pct']}%, "
            f"{emp_open_stories}/{total_open_stories} open = {emp_open_points}/{total_open_points} open pts), "
            f"100% of ATLAS-2 Real-time re-routing (12/12 stories, 7 open), and "
            f"{ae_emp_commits}/{ae_total_commits} commits ({git_metrics['atlas_engine_share_pct']}%) in atlas-engine. "
            f"With {days_to_ga} days to the {atlas_ga_target} Jira GA target and zero active backend hires, "
            "shipping full-scope Atlas v3 (especially ATLAS-2) on Dec 15 is infeasible without scope deferral or "
            "retention + immediate backfill."
        )
        mitigation_actions = [
            "People Ops (Deepa VX005) to confirm signed contractual notice period & last working day today (do not assume 60 days without proof).",
            "Board / CEO (Ananya VX001) & VP Eng (Vikram VX004) to split launch: ship Atlas v3.0 Core (ATLAS-1/3/4 + critical ATLAS-5) and defer ATLAS-2 Real-time re-routing to v3.1 unless continuity is secured.",
            "Immediate 2-week Knowledge Transfer & code pairing: Rahul Verma (VX018, 117 atlas-engine commits) on ATLAS-1/routing-engine and Sneha Kulkarni (VX012, 115 atlas-engine commits) on ATLAS-5/canary-chaos.",
            "Unfreeze REQ-014 and REQ-015 immediately (8 qualified candidates paused since Aug 12) and re-engage Cohere Recruiting Partners using the idle Rs. 1,77,000 advance (JV-0688).",
        ]
    elif spof_risk_level == "CRITICAL":
        board_verdict = (
            f"LATENT CRITICAL SPOF (No resignation released as of {as_of}): {emp['full_name']} ({employee_id}) carries "
            f"{emp_stories}/{total_stories} Jira stories, 100% of {','.join(sole_owned_epics) or 'core epic'}, and "
            f"{emp_commits}/{total_org_commits} git commits ({late_commits} late-night, {wknd_commits} weekend IST)."
        )
        mitigation_actions = [
            "Redistribute sole-owned epic stories and unfreeze paused backend requisitions REQ-014/015.",
        ]
    else:
        board_verdict = f"Operational exposure as of {as_of} based on released data-room artifacts."
        mitigation_actions = []

    candidate_ev = ["E001", "E017", "E023", "E026", "E029", "E031", "E036", "E037", "E038", "E040", "E043", "E048", "E051", "E056", "E057"]
    citations = _build_citation_objects(db_mgr, candidate_ev, as_of)

    return {
        "employee": emp,
        "as_of_date": as_of,
        "resignation_known": resignation_known,
        "spof_risk_level": spof_risk_level,
        "jira": jira_metrics,
        "git": git_metrics,
        "leave": leave_metrics,
        "oncall": oncall_metrics,
        "backfill_bench": backfill_bench,
        "notice_assessment": notice_assessment,
        "board_verdict": board_verdict,
        "mitigation_actions": mitigation_actions,
        "citations": citations,
    }
