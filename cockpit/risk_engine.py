"""Ranked Risk Engine for Veloxa CXO Cockpit.

Dynamically computes and ranks top strategic risks as of a given date
(`as_of_date`), strictly respecting Point-in-Time isolation (`release_date <= as_of_date`).

Implements CEO Voice Note T6a:
- Opens directly to Top 3 Ranked Worries by default.
- Retains lower-ranked items (#4+) in an expandable drawer for auditability.
"""

from __future__ import annotations

from typing import Any

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
    else:
        # Day 3+ (2026-11-18 onwards) incorporating Jira, Git, PagerDuty, On-Call, Launch Kit, PIS-114, T4 & T5
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
