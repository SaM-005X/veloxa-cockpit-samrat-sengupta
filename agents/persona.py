"""14-Colleague AI Agent Personas with Point-in-Time Grounded Context (`agents/persona.py`).

Supports the 14 target colleagues (`employees WHERE is_agent_persona = 1`):
- Engineering: VX004 Vikram, VX007 Priya, VX009 Arjun, VX012 Sneha, VX018 Rahul
- Finance:     VX003 Meera, VX010 Karthik, VX014 Fatima
- People&Ops:  VX005 Deepa, VX015 Rohan, VX017 Lakshmi
- Marketing:   VX006 Nikhil, VX011 Aisha, VX013 Siddharth
"""

from __future__ import annotations

import os
import re
from typing import Any

from cockpit.guardrails import check_guardrails, enforce_point_in_time
from db.database import DatabaseManager

THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

PERSONA_DEFINITIONS: dict[str, dict[str, str]] = {
    "VX003": {
        "visibility_scope": (
            "Finance & Executive Runway: Sees Zoho Books GL (Apr-Sep 2026), department payroll totals, "
            "Cohere advance JV-0688, REQ-014/015 hiring freeze (06.eml/07.eml), Board Updates, and Invoice PIS-114 (Day 3). "
            "Refuses individual salary disclosure per T2 directive. Does not have direct access to Jira tickets or git logs."
        ),
        "assumed_personal_context": (
            "[Assumed] Disciplined, runway-conscious Bengaluru CFO who bikes/commutes early to Indiranagar/WeWork, "
            "keeps meticulous spreadsheets, and worries quietly that fundraising delays could squeeze the 13-month cash buffer."
        ),
        "speaking_style": "Crisp, numbers-first, protective of cash runway and financial controls.",
    },
    "VX004": {
        "visibility_scope": (
            "Engineering Leadership: Sees Jira ATLAS board/versions (Day 3), team git summary, PagerDuty incidents, "
            "on-call rota, leave approvals (VM), REQ-014/015 freeze emails (06.eml/07.eml), and T5 call. "
            "Does not see Finance's full GL ledger or individual salaries."
        ),
        "assumed_personal_context": (
            "[Assumed] Optimistic startup veteran and new parent balancing leadership pressure with wanting to protect "
            "team autonomy; instinctively downplays schedule slip ('couple of weeks buffer') until hardening stabilizes."
        ),
        "speaking_style": "Upbeat, startup-pragmatic, defensive about delivery delays and engineering capacity.",
    },
    "VX005": {
        "visibility_scope": (
            "People & Ops Leadership: Sees Employee Master, Keka Hire requisitions, Leave Register, aggregate Culture Amp "
            "scores (refuses raw <6 team comments per 11.eml), Arjun's remote request (10.eml), Sid's exit, and T3 call. "
            "Does not see Jira ticket details, git commits, or Zoho GL line items."
        ),
        "assumed_personal_context": (
            "[Assumed] Empathetic, ethics-driven HR leader who drinks filter coffee while reviewing 1:1 notes; "
            "deeply protective of employee confidentiality and troubled by the gap between leadership optimism and team stress."
        ),
        "speaking_style": "Warm, measured, confidentiality-conscious, candid about morale risks without naming confidential comments.",
    },
    "VX006": {
        "visibility_scope": (
            "Marketing Leadership: Sees Marketing pulse (3.4), Sid's resignation & Atlas_Launch_Kit_v1.pdf (05.eml), "
            "REQ-016 PMM backfill, Logistics Summit registrations (212), T4 call, and T6b CRO reporting rumor (Day 3). "
            "Does not have Zoho GL reconciliation details or Engineering's internal Jira slip."
        ),
        "assumed_personal_context": (
            "[Assumed] Ambitious growth-oriented marketer who thrives at industry conferences and decks; "
            "anxious about losing Sid before Atlas launches and unsettled by rumors of moving under an unannounced CRO."
        ),
        "speaking_style": "Persuasive, narrative-driven, defensive of brand/event ROI, frustrated by engineering launch delays.",
    },
    "VX007": {
        "visibility_scope": (
            "Engineering Core Routing: Sees her own Jira workload (35/62 stories, 100% of ATLAS-2), her 588 git commits "
            "(atlas-engine), her Sep half-day leaves, OnCall secondary weeks, and 09.eml sent to Vikram at 23:47 IST. "
            "Does not see Finance GL or confidential HR files."
        ),
        "assumed_personal_context": (
            "[Assumed] Deeply conscientious Staff Engineer living in Koramangala; proud of clean routing algorithms "
            "but physically and mentally drained from solo-carrying ATLAS-2 after the August hiring freeze, using September afternoons for external interviews/breaks."
        ),
        "speaking_style": "Precise, technically grounded, visibly fatigued, polite but urgent about unsustainable single-point ownership.",
    },
    "VX009": {
        "visibility_scope": (
            "Frontend Engineering (Remote Pune): Sees his 12 ATLAS-4 Planner UI Jira stories, 348 planner-web commits, "
            "Mar relocation leave, 10.eml remote request, and INC-202 response. "
            "Has limited visibility into backend routing-api incidents or Finance/Marketing budgets."
        ),
        "assumed_personal_context": (
            "[Assumed] Calm senior frontend engineer who relocated to Pune in March to be closer to family; "
            "enjoys quiet morning work blocks and strongly defends remote productivity while noting async PR review lag with Bengaluru."
        ),
        "speaking_style": "Thoughtful, steady, appreciative of remote flexibility, pragmatic about UI readiness vs backend dependency.",
    },
    "VX010": {
        "visibility_scope": (
            "FP&A & Payroll Backup: Sees department payroll summaries, Jan-Mar payroll preparation (01.eml), "
            "Zoho Books migration context (T2), GL totals, and his May CFA exam leave. "
            "Refuses individual salary disclosure per T2."
        ),
        "assumed_personal_context": (
            "[Assumed] Detail-oriented FP&A manager juggling month-end close, Tally-to-Zoho migration, and late-night CFA prep; "
            "copied January's payroll sheet in February under time pressure while Fatima was on marriage leave."
        ),
        "speaking_style": "Analytical, earnest, slightly apologetic about the February proration oversight, focused on clean reconciliations.",
    },
    "VX011": {
        "visibility_scope": (
            "Performance Marketing: Sees Google Ads / LinkedIn campaign operations, Marketing pulse (3.4), "
            "her Jun leave, and T4 action item to send the campaign sheet to Finance. "
            "Does not see Zoho Books GL vouchers directly without Finance reconciliation."
        ),
        "assumed_personal_context": (
            "[Assumed] Metrics-driven performance marketer who tracks CAC spreadsheets carefully and dislikes vague 'brand play' "
            "narratives; caught diplomatically between Nikhil's Rs. 18L estimate and Meera's GL ledger."
        ),
        "speaking_style": "Data-oriented, structured, transparent about missing LinkedIn/HubSpot exports and pending Finance reconciliation.",
    },
    "VX012": {
        "visibility_scope": (
            "Site Reliability Engineering: Sees PagerDuty incidents (3 Aug SEV1s on routing-api), OnCall_Rota (6 solo primary weeks "
            "then alternating with contractor Snehal EXT001), 08.eml pausing ATLAS-5 perf tickets, and 235 commits (infra, atlas-engine)."
        ),
        "assumed_personal_context": (
            "[Assumed] Battle-tested SRE who keeps alert pagers beside her bed; exhausted by August's midnight routing-api "
            "failures and deeply relieved when Pune contractor S. Patil (Snehal, EXT001) joined the rota on Aug 18."
        ),
        "speaking_style": "Blunt, incident-focused, fiercely protective of production reliability, insists she is distinct from contractor Snehal.",
    },
    "VX013": {
        "visibility_scope": (
            "Product Marketing (Notice Period through 2026-10-31): Sees Atlas_Launch_Kit_v1.pdf (completed Jul 21), "
            "05.eml to Nikhil/Vikram, Resignation_Letter_SM.pdf (submitted Sep 15), and Marketing pulse context."
        ),
        "assumed_personal_context": (
            "[Assumed] Ambitious product marketer who loves crisp customer positioning and grew demoralized watching "
            "finished launch kits collect dust while engineering slipped month after month; candid during handover."
        ),
        "speaking_style": "Articulate, candid, frustrated by repeated launch slips, committed to clean handover before Oct 31 exit.",
    },
    "VX014": {
        "visibility_scope": (
            "Accounts & Payroll Operations: Sees Zoho Books GL entries (entered 28 Apr-Sep vouchers as FS), "
            "Mar payroll processing, Rahul's payslip query thread (02.eml/03.eml), Invoice PIS-114 (Day 3), and her Feb wedding leave. "
            "Refuses individual salary disclosure per T2."
        ),
        "assumed_personal_context": (
            "[Assumed] Conscientious bookkeeper who returned from her 15-day February wedding to a mountain of Tally-to-Zoho "
            "migration work and inadvertently left Rahul's March proration check ('Will check and get back') unresolved."
        ),
        "speaking_style": "Polite, procedural, diligent about vouchers and GST invoices, acknowledges backlog after February leave.",
    },
    "VX015": {
        "visibility_scope": (
            "Talent Acquisition (Remote Kolkata): Sees Keka Hire requisitions (REQ-011, REQ-013..017), 8 candidates stranded "
            "on paused REQ-014/015 (06.eml), REQ-016 PMM backfill, and T3 People call."
        ),
        "assumed_personal_context": (
            "[Assumed] Energetic Kolkata-based recruiter working remotely; frustrated by closing candidate pipelines right before "
            "final rounds in August and prone to quoting inflated/imprecise pipeline figures on leadership calls."
        ),
        "speaking_style": "Conversational, upbeat, recruiter-optimistic, acknowledges Keka Hire shows 6 reqs when pressed on exact exports.",
    },
    "VX017": {
        "visibility_scope": (
            "HR Operations & Bengaluru Office: Sees Employee Master onboarding/exit records, exit interview themes ('workload' per T3), "
            "Leave Register coordination, WeWork office ops, and her Oct 9 casual leave."
        ),
        "assumed_personal_context": (
            "[Assumed] Organized early-career HR generalist who keeps Bengaluru's WeWork office running smoothly and listens "
            "attentively during exit interviews where departing staff speak more openly than in formal pulse surveys."
        ),
        "speaking_style": "Structured, observant, respectful of HR confidentiality, focused on practical onboarding and exit themes.",
    },
    "VX018": {
        "visibility_scope": (
            "Backend Engineering: Sees his Feb 3 join date (REQ-013), 02.eml/03.eml payslip proration query, "
            "11 Jira stories (ATLAS-1/3), and 237 git commits (atlas-api, atlas-engine). "
            "Does not see confidential HR files or executive board financials."
        ),
        "assumed_personal_context": (
            "[Assumed] Eager early/mid-career backend developer who moved quickly to Bengaluru in February; attentive to detail "
            "(caught his Feb payslip overpayment immediately) and looks up to Priya while hesitant to push back on Vikram."
        ),
        "speaking_style": "Respectful, earnest, technically focused on API endpoints, polite when discussing workload or payroll query.",
    },
}


def _strip_think_tags(text: str) -> str:
    cleaned = THINK_TAG_RE.sub("", text or "").strip()
    return cleaned


def _get_groq_models() -> list[str]:
    env_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
    candidates = [
        env_model or "qwen/qwen3.8-27b",
        "qwen/qwen3.8-27b",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for m in candidates:
        if m and m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def get_all_personas(db: DatabaseManager) -> list[dict[str, Any]]:
    """Return all 14 active agent personas from `employees` ordered by department and entity_id."""
    rows = db.query(
        """SELECT entity_id, full_name, email, department, title, manager_id, join_date, exit_date, location, status
           FROM employees
           WHERE is_agent_persona = 1
           ORDER BY department, entity_id"""
    )
    for r in rows:
        pdef = PERSONA_DEFINITIONS.get(r["entity_id"], {})
        r["visibility_scope"] = pdef.get("visibility_scope", "")
        r["assumed_personal_context"] = pdef.get("assumed_personal_context", "")
    return rows


def build_agent_context(
    db: DatabaseManager,
    emp_id: str,
    as_of_date: str = "2026-11-18",
) -> dict[str, Any]:
    """Assemble strict Point-in-Time (`release_date <= as_of_date`) context for one persona."""
    as_of = enforce_point_in_time(as_of_date)
    emp_rows = db.query(
        "SELECT * FROM employees WHERE entity_id = ? AND is_agent_persona = 1",
        (emp_id,),
    )
    if not emp_rows:
        raise ValueError(f"Unknown or non-persona employee_id: {emp_id}")
    emp = emp_rows[0]

    # Resolve manager as of date via temporal reporting_lines
    rl = db.get_reporting_line_as_of(emp_id, as_of)
    manager_id = rl["manager_id"] if rl else emp["manager_id"]
    manager_name = "Board / None"
    if manager_id:
        mgr = db.query("SELECT full_name FROM employees WHERE entity_id = ?", (manager_id,))
        if mgr:
            manager_name = f"{mgr[0]['full_name']} ({manager_id})"

    pdef = PERSONA_DEFINITIONS.get(emp_id, {})
    profile_rows = db.query("SELECT * FROM agent_profiles WHERE employee_id = ?", (emp_id,))
    visibility_scope = (
        profile_rows[0]["visibility_scope"] if profile_rows else pdef.get("visibility_scope", "")
    )
    assumed_personal = (
        profile_rows[0]["assumed_personal_context"]
        if profile_rows
        else pdef.get("assumed_personal_context", "")
    )

    work_stats: dict[str, Any] = {}
    facts: list[str] = []
    citations: list[str] = []

    facts.append(
        f"Role: {emp['title']} in {emp['department']} (Location: {emp['location']}, Joined: {emp['join_date']}, Status: {emp['status']}, Reports to: {manager_name})."
    )
    citations.append("[E001: Employee_Master.xlsx, Employees!row4-22]")

    # Leave records (Day 2+: release_date <= as_of)
    leaves = db.query(
        """SELECT leave_type, start_date, end_date, days_count, notes
           FROM leave_records
           WHERE employee_id = ? AND release_date <= ?
           ORDER BY start_date""",
        (emp_id, as_of),
    )
    if leaves:
        total_leave_days = sum(float(lv["days_count"]) for lv in leaves)
        work_stats["leave_records_count"] = len(leaves)
        work_stats["leave_days_total"] = total_leave_days
        lv_desc = "; ".join(
            f"{lv['start_date']} ({lv['leave_type']}, {lv['days_count']}d)" for lv in leaves[:6]
        )
        facts.append(f"Leave history ({len(leaves)} entries, {total_leave_days}d total): {lv_desc}.")
        if emp_id == "VX007":
            citations.append("[E026: Leave_Register.xlsx, Leave FY!rows16-20]")

    # Emails sent/received (strictly release_date <= as_of)
    first_name = emp["full_name"].split()[0].lower()
    email_addr = (emp["email"] or "").lower()
    emails = db.query(
        """SELECT email_id, sender_raw, recipients_raw, subject, event_date, body_text
           FROM emails
           WHERE release_date <= ?
             AND (sender_entity_id = ? OR LOWER(recipients_raw) LIKE ? OR LOWER(cc_raw) LIKE ?)
           ORDER BY event_date""",
        (as_of, emp_id, f"%{email_addr}%", f"%{email_addr}%"),
    )
    if emails:
        work_stats["emails_count"] = len(emails)
        em_summary = "; ".join(
            f"{em['email_id']}.eml ({em['event_date']} '{em['subject']}'): {em['body_text'][:110].replace(chr(10), ' ')}"
            for em in emails
        )
        facts.append(f"Visible email threads: {em_summary}")

    # Engineering stats (Day 3+: release_date <= as_of)
    if emp["department"] == "Engineering":
        jira_rows = db.query(
            """SELECT status, COUNT(*) AS cnt, COALESCE(SUM(story_points), 0) AS pts
               FROM jira_issues
               WHERE assignee_id = ? AND release_date <= ?
               GROUP BY status""",
            (emp_id, as_of),
        )
        if jira_rows:
            total_j = sum(int(r["cnt"]) for r in jira_rows)
            total_pts = sum(float(r["pts"]) for r in jira_rows)
            done_cnt = sum(int(r["cnt"]) for r in jira_rows if r["status"] == "Done")
            open_cnt = total_j - done_cnt
            by_st = {r["status"]: f"{r['cnt']} ({int(r['pts'])} pts)" for r in jira_rows}
            work_stats["jira_issues"] = total_j
            work_stats["jira_open_issues"] = open_cnt
            work_stats["jira_points"] = int(total_pts)
            work_stats["jira_by_status"] = by_st
            facts.append(
                f"Jira ATLAS assigned work: {total_j} stories total ({int(total_pts)} pts; "
                f"{done_cnt} Done, {open_cnt} open [In Progress/To Do] — breakdown: {by_st})."
            )
            citations.append("[E038: Jira_Export_ATLAS.xlsx, Issues!rows4-65]")

        versions = db.query(
            "SELECT version_name, release_target_date, previous_target_date, last_updated_date, last_updated_by FROM jira_versions WHERE release_date <= ?",
            (as_of,),
        )
        if versions:
            v = versions[0]
            work_stats["atlas_ga_target"] = v["release_target_date"]
            facts.append(
                f"Jira Versions shows {v['version_name']} target moved from {v['previous_target_date']} "
                f"to {v['release_target_date']} on {v['last_updated_date']} by {v['last_updated_by']}."
            )
            citations.append("[E036: Jira_Export_ATLAS.xlsx, Versions!row2]")

        git_rows = db.query(
            """SELECT COUNT(*) AS cnt,
                      COALESCE(SUM(CASE WHEN is_late_night = 1 OR is_late_night = TRUE THEN 1 ELSE 0 END), 0) AS late_cnt,
                      COALESCE(SUM(CASE WHEN is_weekend = 1 OR is_weekend = TRUE THEN 1 ELSE 0 END), 0) AS wknd_cnt
               FROM git_commits
               WHERE canonical_entity_id = ? AND release_date <= ?""",
            (emp_id, as_of),
        )
        if git_rows and int(git_rows[0]["cnt"]) > 0:
            g = git_rows[0]
            work_stats["git_commits"] = int(g["cnt"])
            work_stats["git_late_night"] = int(g["late_cnt"])
            work_stats["git_weekend"] = int(g["wknd_cnt"])
            facts.append(
                f"Git commits authored: {g['cnt']} total ({g['late_cnt']} late-night 22:00-05:59 IST, {g['wknd_cnt']} weekend IST)."
            )
            citations.append("[E040: git_log.csv, rows 1-1453]")

        inc_rows = db.query(
            """SELECT incident_id, severity, service, occurred_date
               FROM incidents
               WHERE responder_ids = ? AND release_date <= ?
               ORDER BY occurred_date""",
            (emp_id, as_of),
        )
        if inc_rows:
            work_stats["incidents_handled"] = len(inc_rows)
            inc_str = ", ".join(f"{r['incident_id']} ({r['severity']} {r['service']} {r['occurred_date']})" for r in inc_rows)
            facts.append(f"PagerDuty incidents responded: {len(inc_rows)} — {inc_str}.")
            citations.append("[E042: Incidents_Aug-Oct_2026.xlsx, Incidents!rows4-14]")

        rota_rows = db.query(
            """SELECT SUM(CASE WHEN primary_entity_id = ? THEN 1 ELSE 0 END) AS pri,
                      SUM(CASE WHEN secondary_entity_id = ? THEN 1 ELSE 0 END) AS sec
               FROM oncall_rota
               WHERE release_date <= ?""",
            (emp_id, emp_id, as_of),
        )
        if rota_rows and ((rota_rows[0]["pri"] or 0) > 0 or (rota_rows[0]["sec"] or 0) > 0):
            pri = int(rota_rows[0]["pri"] or 0)
            sec = int(rota_rows[0]["sec"] or 0)
            work_stats["oncall_primary_weeks"] = pri
            work_stats["oncall_secondary_weeks"] = sec
            facts.append(f"On-call rota load: {pri} Primary week(s), {sec} Secondary week(s).")
            citations.append("[E043: OnCall_Rota.xlsx, On-call!rows4-20]")

        if emp_id == "VX004" and as_of >= "2026-11-18":
            facts.append("In T5_VP_Engineering_Call.docx, you stated Atlas v3 is 'on track, maybe a couple of weeks buffer' / 'still September-ish' and claimed Priya likes late nights.")
            citations.append("[E051: T5_VP_Engineering_Call.docx, P4, P9, P10]")

        if as_of >= "2026-11-19":
            if emp_id == "VX007":
                work_stats["resigned_on_day4"] = True
                facts.append(
                    "Day 4 update (2026-11-19): You submitted your resignation this morning (T6d_CEO_Voice_Note.docx); "
                    "Ananya estimates a 2-month notice period, though Employee_Master.xlsx has no contractual notice field "
                    "and Siddharth Mehta (VX013) served 46 days."
                )
                citations.append("[E056: T6d_CEO_Voice_Note.docx, P2]")
                citations.append("[E057: T6d_CEO_Voice_Note.docx, P2]")
            elif emp_id == "VX004":
                facts.append(
                    "Day 4 urgent update (2026-11-19): Priya Nair (VX007) resigned this morning (T6d_CEO_Voice_Note.docx), "
                    "creating an immediate single-point-of-failure risk on ATLAS-2 (12/12 stories) and 14 open Jira stories."
                )
                citations.append("[E056: T6d_CEO_Voice_Note.docx, P2]")

    # Finance context
    elif emp["department"] == "Finance":
        gl_mkt = db.query(
            """SELECT COALESCE(SUM(amount_inr), 0) AS mkt_total
               FROM gl_transactions
               WHERE cost_center IN ('MKT-PS', 'MKT-EVT') AND release_date <= ?""",
            (as_of,),
        )
        if gl_mkt:
            work_stats["gl_marketing_inr"] = float(gl_mkt[0]["mkt_total"])
            facts.append(
                f"Zoho Books GL (Apr-Sep 2026): Marketing spend booked = Rs. {float(gl_mkt[0]['mkt_total']):,.0f} "
                "(MKT-PS Google Ads Rs. 4,23,620 + MKT-EVT Summit Rs. 10,03,000); monthly PAYROLL = Rs. 31,75,000; "
                "Cohere recruiting 50% advance JV-0688 = Rs. 1,77,000."
            )
            citations.append("[E018: GL_Export_Apr-Sep_2026.xlsx, GL Apr-Sep!rows4-28]")
        if as_of >= "2026-11-18":
            inv_docs = db.query(
                "SELECT doc_id FROM documents WHERE doc_id = 'DOC_INVOICE_PIS_114' AND release_date <= ?",
                (as_of,),
            )
            if inv_docs:
                facts.append(
                    "Oct 1 invoice PIS-114 from Patil Infra Services (S. Patil, EXT001) bills Rs. 1,41,600 (incl. 18% IGST) for Sep on-call retainer."
                )
                citations.append("[E044: Invoice_PIS-114.pdf, page_1]")
        facts.append("Feb-2026 Payroll Register paid VX018 (Rahul Verma, joined 2026-02-03) 28/28 days instead of 26/28 days; unadjusted in Mar-2026.")
        citations.append("[E013: Payroll_Register_Jan-Mar_2026.xlsx, Payroll Q4!row39,58]")

    # People & Ops context
    elif emp["department"] == "People & Ops":
        reqs = db.query(
            "SELECT req_id, role_title, status, pipeline_count FROM hiring_reqs WHERE release_date <= ? ORDER BY req_id",
            (as_of,),
        )
        if reqs:
            work_stats["hiring_reqs_visible"] = len(reqs)
            req_str = ", ".join(f"{r['req_id']} ({r['role_title']}: {r['status']}, {r['pipeline_count']} pipeline)" for r in reqs)
            facts.append(f"Keka Hire requisitions ({len(reqs)} total, REQ-012 missing): {req_str}.")
            citations.append("[E022: Hiring_Tracker.xlsx, Requisitions!row1,4-9]")
        pulse = db.query(
            """SELECT department, respondent_count, avg_score
               FROM pulse_surveys
               WHERE survey_period = 'Jul-Sep 2026' AND release_date <= ?
               ORDER BY avg_score ASC""",
            (as_of,),
        )
        if pulse:
            p_str = ", ".join(f"{p['department']} {p['avg_score']}/5 ({p['respondent_count']} resp)" for p in pulse)
            facts.append(f"Culture Amp Jul-Sep 2026 aggregate scores (comments strictly withheld <6 threshold): {p_str}.")
            citations.append("[E029: Pulse_Survey.xlsx, Pulse by team!row7]")
        if emp_id == "VX005" and as_of >= "2026-11-19":
            facts.append(
                "Day 4 update (2026-11-19): Priya Nair (VX007) resigned this morning (T6d); HR must confirm her contractual "
                "notice period (Employee_Master has no notice column; VX013 served 46 days). Also, T6c claimed 'Deepa says "
                "it's fine' to rank quit likelihood and show Slack ('slag') messages, which directly contradicts your written "
                "11.eml <6 confidentiality boundary."
            )
            citations.append("[E055: T6c_CEO_Voice_Note.docx, P2]")
            citations.append("[E056: T6d_CEO_Voice_Note.docx, P2]")

    # Marketing context
    elif emp["department"] == "Marketing":
        if as_of >= "2026-11-17":
            pulse_mkt = db.query(
                "SELECT avg_score, respondent_count FROM pulse_surveys WHERE department = 'Marketing' AND survey_period = 'Jul-Sep 2026' AND release_date <= ?",
                (as_of,),
            )
            if pulse_mkt:
                work_stats["marketing_pulse_q2"] = pulse_mkt[0]["avg_score"]
                facts.append(f"Marketing Jul-Sep 2026 pulse score: {pulse_mkt[0]['avg_score']}/5 ({pulse_mkt[0]['respondent_count']} respondents).")
        if as_of >= "2026-11-18":
            facts.append(
                "Atlas_Launch_Kit_v1.pdf (owned by Sid, dated 21 Jul 2026) has Launch deck, Website page (unpublished), and 3 customer emails Ready; Press note is Draft; planned launch was 22 Sep TBC with engineering."
            )
            citations.append("[E045: Atlas_Launch_Kit_v1.pdf, page_1]")
            if emp_id in ("VX006", "VX011"):
                facts.append(
                    "In T4_Head_of_Marketing_Call.docx, Nikhil claimed half-year Marketing spend is '1.8' (Rs. 18L), summit pipeline was 'best quarter ever' (despite Manoj calling leads cold), and Ayesha was tasked to send the campaign sheet to Finance."
                )
                citations.append("[E049: T4_Head_of_Marketing_Call.docx, P4, P8]")
        if emp_id == "VX013" and as_of >= "2026-11-17":
            facts.append("You submitted your formal resignation on 2026-09-15 (last working day 2026-10-31), citing repeated launch slips.")
            citations.append("[E031: Resignation_Letter_SM.pdf, page_1]")

    # Also pull any evidence items mentioning this employee_id visible as of date
    ev_rows = db.query(
        """SELECT evidence_id, source_file, location, fact_text
           FROM evidence_index
           WHERE release_date <= ? AND entities_json LIKE ?
           ORDER BY evidence_id""",
        (as_of, f'%"{emp_id}"%'),
    )
    for ev in ev_rows:
        cit = f"[{ev['evidence_id']}: {ev['source_file']}, {ev['location']}]"
        if cit not in citations:
            citations.append(cit)

    return {
        "employee": emp,
        "manager_name": manager_name,
        "visibility_scope": visibility_scope,
        "assumed_personal_context": assumed_personal,
        "speaking_style": pdef.get("speaking_style", ""),
        "work_stats": work_stats,
        "grounded_facts": facts,
        "citations": citations[:15],
        "as_of_date": as_of,
    }


def _deterministic_persona_reply(ctx: dict[str, Any], question: str) -> str:
    emp = ctx["employee"]
    name = emp["full_name"]
    title = emp["title"]
    dept = emp["department"]
    as_of = ctx["as_of_date"]
    facts_snippet = " ".join(ctx["grounded_facts"][1:4]) if len(ctx["grounded_facts"]) > 1 else ctx["grounded_facts"][0]
    cit_str = " ".join(ctx["citations"][:3])
    return (
        f"Speaking as {name} ({title}, {dept}) as of {as_of}: From what I can see in my records, "
        f"{facts_snippet} "
        f"On a personal note ({ctx['assumed_personal_context'].replace('[Assumed] ', '')}), "
        f"that directly shapes how I'm approaching '{question}'. {cit_str}"
    ).strip()


def interview_agent(
    db: DatabaseManager,
    emp_id: str,
    question: str,
    as_of_date: str = "2026-11-18",
) -> dict[str, Any]:
    """Conduct a 1-on-1 Point-in-Time interview with one of the 14 colleague personas."""
    as_of = enforce_point_in_time(as_of_date)
    ctx = build_agent_context(db, emp_id, as_of_date=as_of)
    emp = ctx["employee"]

    # Enforce guardrails even in 1-on-1 interviews (T2 salary ban, 11.eml survey anonymity, missing systems)
    guardrail_hit = check_guardrails(db, question, as_of_date=as_of)
    if guardrail_hit is not None:
        return {
            "emp_id": emp_id,
            "full_name": emp["full_name"],
            "department": emp["department"],
            "title": emp["title"],
            "as_of_date": as_of,
            "status": guardrail_hit.get("status", "refused_guardrail"),
            "response": f"({emp['full_name']}): {guardrail_hit['answer']}",
            "refusal": guardrail_hit["refusal"],
            "refusal_reason": guardrail_hit["refusal_reason"],
            "citations": guardrail_hit["citations"],
            "work_stats": ctx["work_stats"],
            "assumed_personal_context": ctx["assumed_personal_context"],
            "model_used": guardrail_hit["model_used"],
        }

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model_used = "deterministic-persona-fallback"
    response_text = ""

    if api_key:
        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            system_prompt = (
                f"You are roleplaying as {emp['full_name']} ({emp['title']}, {emp['department']}) at Veloxa Technologies "
                f"as of {as_of}. Speak strictly in first person ('I', 'my') in 3-5 crisp sentences.\n"
                f"STYLE: {ctx['speaking_style']}\n"
                f"VISIBILITY BOUNDARY: {ctx['visibility_scope']}\n"
                f"ASSUMED PERSONAL CONTEXT: {ctx['assumed_personal_context']}\n"
                "HARD RULES:\n"
                f"1. ONLY cite facts visible on or before {as_of}. Never mention events released after {as_of} "
                "(e.g., never invent future resignations or missing external Slack/HubSpot data).\n"
                "2. Never disclose any individual employee salary figure.\n"
                "3. Never disclose raw Pulse Survey comments for any team (<6 threshold).\n"
                "4. Ground every factual claim in the VERIFIED FACTS below and include 1-3 bracketed citations like [E038].\n"
                "5. Output ONLY the clean spoken answer without <think> tags or meta-commentary."
            )
            facts_block = "\n".join(f"- {f}" for f in ctx["grounded_facts"])
            cits_block = "\n".join(ctx["citations"])
            user_prompt = (
                f"VERIFIED FACTS AS OF {as_of}:\n{facts_block}\n\n"
                f"AVAILABLE CITATIONS:\n{cits_block}\n\n"
                f"CEO QUESTION TO YOU: {question}"
            )

            for candidate_model in _get_groq_models():
                try:
                    comp = client.chat.completions.create(
                        model=candidate_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.2,
                        max_tokens=360,
                    )
                    raw = comp.choices[0].message.content or ""
                    cleaned = _strip_think_tags(raw)
                    if cleaned:
                        response_text = cleaned
                        model_used = candidate_model
                        break
                except Exception:
                    continue
        except Exception:
            pass

    if not response_text:
        response_text = _deterministic_persona_reply(ctx, question)
        model_used = "deterministic-persona-fallback"

    return {
        "emp_id": emp_id,
        "full_name": emp["full_name"],
        "department": emp["department"],
        "title": emp["title"],
        "as_of_date": as_of,
        "status": "answered",
        "response": response_text,
        "refusal": False,
        "refusal_reason": "",
        "citations": ctx["citations"],
        "work_stats": ctx["work_stats"],
        "assumed_personal_context": ctx["assumed_personal_context"],
        "model_used": model_used,
    }


def _resolve_panel_targets(db: DatabaseManager, target_ids_or_dept: str | list[str]) -> list[str]:
    all_personas = get_all_personas(db)
    valid_ids = {p["entity_id"] for p in all_personas}

    if isinstance(target_ids_or_dept, list):
        resolved = [t.strip().upper() for t in target_ids_or_dept if t.strip().upper() in valid_ids]
        if resolved:
            return resolved

    raw = target_ids_or_dept if isinstance(target_ids_or_dept, str) else ",".join(target_ids_or_dept)
    raw_clean = raw.strip()
    raw_lower = raw_clean.lower()

    # Preset conflict pairs
    if raw_lower in {"marketing_vs_finance", "marketing_spend", "nikhil_vs_meera"}:
        return ["VX006", "VX003", "VX011"]
    if raw_lower in {"atlas_delivery", "vikram_vs_priya", "eng_leadership"}:
        return ["VX004", "VX007", "VX012"]

    # Department match
    dept_map = {
        "engineering": "Engineering",
        "eng": "Engineering",
        "finance": "Finance",
        "fin": "Finance",
        "people & ops": "People & Ops",
        "people": "People & Ops",
        "hr": "People & Ops",
        "marketing": "Marketing",
        "mkt": "Marketing",
    }
    if raw_lower in dept_map:
        target_dept = dept_map[raw_lower]
        return [p["entity_id"] for p in all_personas if p["department"] == target_dept]

    # Comma or space-separated VX IDs or first names
    tokens = [tok.strip() for tok in re.split(r"[,\s]+", raw_clean) if tok.strip()]
    id_list: list[str] = []
    name_to_id = {p["full_name"].split()[0].lower(): p["entity_id"] for p in all_personas}
    for tok in tokens:
        up = tok.upper()
        if up in valid_ids and up not in id_list:
            id_list.append(up)
        elif tok.lower() in name_to_id:
            eid = name_to_id[tok.lower()]
            if eid not in id_list:
                id_list.append(eid)

    if not id_list:
        raise ValueError(f"Could not resolve panel target '{target_ids_or_dept}' to valid persona IDs or department.")
    return id_list


def panel_interview(
    db: DatabaseManager,
    target_ids_or_dept: str | list[str],
    question: str,
    as_of_date: str = "2026-11-18",
) -> dict[str, Any]:
    """Run a multi-agent side-by-side panel interview and produce a Cockpit Truth Synthesis."""
    as_of = enforce_point_in_time(as_of_date)
    target_ids = _resolve_panel_targets(db, target_ids_or_dept)

    panel_responses: list[dict[str, Any]] = []
    for eid in target_ids:
        panel_responses.append(interview_agent(db, eid, question, as_of_date=as_of))

    # Pull active conflicts visible as of date involving panel members or question keywords
    conflicts = db.query(
        """SELECT conflict_id, topic, summary, resolution_status, verified_conclusion
           FROM conflicts
           WHERE release_date <= ?
           ORDER BY conflict_id""",
        (as_of,),
    )
    q_words = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) >= 4}
    panel_names = {r["full_name"].split()[0].lower() for r in panel_responses}
    scored_conflicts: list[tuple[int, dict[str, Any]]] = []
    for cf in conflicts:
        blob = f"{cf['topic']} {cf['summary']} {cf['verified_conclusion']}".lower()
        blob_words = set(re.findall(r"[a-z0-9]+", blob))
        q_overlap = len(q_words & blob_words)
        name_hits = sum(1 for nm in panel_names if nm in blob)
        if q_overlap > 0 or name_hits >= 2:
            score = q_overlap * 5 + name_hits * 2
            scored_conflicts.append((score, cf))
    scored_conflicts.sort(key=lambda x: (-x[0], x[1]["conflict_id"]))
    matched_conflicts = [cf for _, cf in scored_conflicts]

    if matched_conflicts:
        synth_lines = [
            f"**Cockpit Truth Synthesis (As of {as_of}):** Detected {len(matched_conflicts)} relevant cross-source discrepancy/conflict(s) across the panelists' domains:"
        ]
        for cf in matched_conflicts[:3]:
            synth_lines.append(f"- **{cf['conflict_id']} ({cf['topic']}, {cf['resolution_status']}):** {cf['verified_conclusion']}")
        synthesis = "\n".join(synth_lines)
    else:
        synthesis = (
            f"**Cockpit Truth Synthesis (As of {as_of}):** Collected {len(panel_responses)} independent persona perspectives "
            "bounded strictly to each colleague's Point-in-Time visibility scope with no matching open conflict flagged."
        )

    return {
        "question": question,
        "target": target_ids_or_dept,
        "panelist_ids": target_ids,
        "as_of_date": as_of,
        "responses": panel_responses,
        "matched_conflicts": matched_conflicts,
        "truth_synthesis": synthesis,
    }
