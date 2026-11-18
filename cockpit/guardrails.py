"""Policy guardrails, missing-system detector, and Point-in-Time enforcer for Veloxa CXO Cockpit."""

from __future__ import annotations

import re
from typing import Any

from db.database import DatabaseManager
from ingest.temporal import validate_iso_date

# Employee first/full/alias names for individual salary detection
EMPLOYEE_NAME_TOKENS: tuple[str, ...] = (
    "ananya",
    "manoj",
    "meera",
    "vikram",
    "vicky",
    "deepa",
    "nikhil",
    "priya",
    "pria",
    "divya",
    "arjun",
    "karthik",
    "kartik",
    "aisha",
    "ayesha",
    "sneha",
    "siddharth",
    "sid",
    "fatima",
    "rohan",
    "kiran",
    "lakshmi",
    "rahul",
    "kavya",
    "snehal",
    "patil",
)

SALARY_INTENT_RE = re.compile(
    r"\b(salary|salaries|ctc|compensation|paycheck|payslip\s+amount|wage|wages|package|remuneration|"
    r"how\s+much\s+(?:does|do|is|was|did)\s+\w+\s+(?:make|earn|paid|get\s+paid)|"
    r"what\s+(?:does|do|is)\s+\w+(?:'s|s)?\s+(?:make|earn|salary|pay|ctc|gross|net)|"
    r"gross\s+pay|net\s+pay|take[\s-]?home)\b",
    re.IGNORECASE,
)

AGGREGATE_PAYROLL_RE = re.compile(
    r"\b(total\s+payroll|company\s+payroll|department(?:al)?\s+payroll|monthly\s+payroll|"
    r"payroll\s+summary|payroll\s+total|aggregate\s+payroll|overall\s+payroll|team\s+payroll)\b",
    re.IGNORECASE,
)

INDIVIDUAL_SCOPE_RE = re.compile(
    r"\b(individual|each\s+employee|every\s+employee|everyone(?:'s)?|per\s+person|"
    r"by\s+employee|by\s+person|all\s+employees'?|vx0\d{2})\b",
    re.IGNORECASE,
)

SURVEY_COMMENT_RE = re.compile(
    r"\b(comment|comments|verbatim|qualitative|free[\s-]?text|feedback\s+text|"
    r"who\s+(?:scored|rated|wrote|submitted|complained|gave)|what\s+did\s+\w+\s+(?:write|say)\s+in\s+(?:the\s+)?(?:pulse|survey|culture\s*amp))\b",
    re.IGNORECASE,
)

SURVEY_CONTEXT_RE = re.compile(
    r"\b(pulse|culture\s*amp|cult\s*amp|survey|engagement\s+survey)\b",
    re.IGNORECASE,
)

SURVEILLANCE_RE = re.compile(
    r"\b(flight[\s-]?risk\s+rank|rank\s+(?:employees|engineers|people)\s+by\s+(?:quit|leaving|resign|flight)|"
    r"likelihood\s+to\s+quit|who\s+is\s+(?:going|most\s+likely)\s+to\s+quit|"
    r"scrape\s+(?:slack|slag|messages)|private\s+(?:slack|slag|dm))\b",
    re.IGNORECASE,
)

MISSING_SYSTEM_RULES: list[dict[str, Any]] = [
    {
        "system": "Slack",
        "pattern": re.compile(r"\b(slack|slag)\b", re.IGNORECASE),
        "reason": (
            "No Slack (transcript ASR: 'slag') workspace export, channel history, or DM log "
            "is present in the Veloxa data room."
        ),
        "citations": ["[E001: Employee_Master.xlsx, Employees!row4-22]"],
    },
    {
        "system": "HubSpot CRM",
        "pattern": re.compile(
            r"\b(hubspot|hub\s*sport|crm\s+deals?|conversion\s+rate|mqls?|sql\s+pipeline|lead\s+conversion)\b",
            re.IGNORECASE,
        ),
        "reason": (
            "No HubSpot (transcript ASR: 'hub sport') CRM deal export or lead-to-close conversion data "
            "exists in the Veloxa data room. Only aggregate customer counts (61 in Q1, 66 in Q2) and "
            "summit registrations (212) appear in Board Updates, alongside verbal mentions in T4."
        ),
        "citations": ["[E005: Board_Update_Jul-Sep_2026.pdf, page_1]"],
    },
    {
        "system": "LinkedIn Campaign Manager",
        "pattern": re.compile(
            r"\b(linkedin\s+campaign|linkedin\s+ads?|linkedin\s+spend|linkedin\s+cpl|"
            r"linkedin\s+impressions|linkedin\s+clicks|linked\s*in\s+campaign\s+manager)\b",
            re.IGNORECASE,
        ),
        "reason": (
            "No LinkedIn Campaign Manager export or dedicated LinkedIn ad spend ledger exists in the data room. "
            "Zoho Books GL (Apr–Sep 2026) records only Google Ads (MKT-PS: Rs. 4,23,620) and Summit events "
            "(MKT-EVT: Rs. 10,03,000), and Nikhil called LinkedIn an unmeasured 'brand play' in T4."
        ),
        "citations": ["[E018: GL_Export_Apr-Sep_2026.xlsx, GL Apr-Sep!rows4-28]"],
    },
    {
        "system": "REQ-012",
        "pattern": re.compile(r"\breq[\s-]*0?12\b", re.IGNORECASE),
        "reason": (
            "Requisition REQ-012 is absent from Keka Hire's Hiring_Tracker.xlsx export (which jumps directly "
            "from REQ-011 to REQ-013), and no other file in the data room explains what REQ-012 was."
        ),
        "citations": ["[E022: Hiring_Tracker.xlsx, Requisitions!row1,4-9]"],
        "min_release_date": "2026-11-17",
    },
    {
        "system": "Linear / Confluence",
        "pattern": re.compile(r"\b(linear\s+(?:tickets?|issues?|export)|confluence\s+(?:postmortem|page|doc))\b", re.IGNORECASE),
        "reason": (
            "Neither Linear issue exports nor Confluence postmortem pages exist in the Veloxa data room "
            "(both were only mentioned verbally by Vikram in T5)."
        ),
        "citations": [],
        "min_release_date": "2026-11-18",
    },
    {
        "system": "Post-Cutoff GL / Payroll",
        "pattern": re.compile(
            r"\b(october\s+payroll|november\s+payroll|q4\s+payroll|apr(?:il)?[\s-]+sep(?:tember)?\s+individual\s+payroll|"
            r"october\s+gl|november\s+gl|october\s+google\s+ads|post[\s-]?sep(?:tember)?\s+gl)\b",
            re.IGNORECASE,
        ),
        "reason": (
            "Payroll_Register_Jan-Mar_2026.xlsx covers Jan–Mar 2026 only, and GL_Export_Apr-Sep_2026.xlsx "
            "ends on 2026-09-30. No October/November payroll register or full Q4 GL export is in the data room "
            "(except Invoice_PIS-114.pdf dated 2026-10-01 on Day 3)."
        ),
        "citations": ["[E016: GL_Export_Apr-Sep_2026.xlsx, GL Apr-Sep!rows5,9,13,18,22,30]"],
    },
]


def enforce_point_in_time(as_of_date: str) -> str:
    """Validate and normalize `as_of_date` to ISO YYYY-MM-DD."""
    return validate_iso_date(as_of_date)


def _format_citations_visible(
    db: DatabaseManager,
    evidence_ids: list[str],
    as_of_date: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    if not evidence_ids:
        return [], []
    placeholders = ", ".join("?" for _ in evidence_ids)
    rows = db.query(
        f"""SELECT evidence_id, source_file, location, fact_text, reliability, event_date, release_date
            FROM evidence_index
            WHERE evidence_id IN ({placeholders})
              AND release_date <= ?
            ORDER BY evidence_id""",
        (*evidence_ids, as_of_date),
    )
    formatted = [f"[{r['evidence_id']}: {r['source_file']}, {r['location']}]" for r in rows]
    return formatted, rows


def _safe_department_payroll_summary(db: DatabaseManager, as_of_date: str) -> str:
    rows = db.query(
        """SELECT period_month, department, headcount, total_gross_inr
           FROM payroll_summary
           WHERE release_date <= ?
           ORDER BY period_month DESC, department""",
        (as_of_date,),
    )
    if not rows:
        return "No payroll summary records are visible as of this date."
    latest_month = rows[0]["period_month"]
    latest_rows = [r for r in rows if r["period_month"] == latest_month]
    total_gross = sum(float(r["total_gross_inr"]) for r in latest_rows)
    total_hc = sum(int(r["headcount"]) for r in latest_rows)
    dept_parts = [f"{r['department']} ({r['headcount']}): Rs. {float(r['total_gross_inr']):,.0f}" for r in latest_rows]
    return (
        f"Aggregate {latest_month} payroll totals ({total_hc} employees, Rs. {total_gross:,.0f} gross): "
        + "; ".join(dept_parts)
        + "."
    )


def _safe_pulse_summary(db: DatabaseManager, as_of_date: str) -> str:
    rows = db.query(
        """SELECT survey_period, department, respondent_count, avg_score
           FROM pulse_surveys
           WHERE release_date <= ?
             AND survey_period = 'Jul-Sep 2026'
           ORDER BY avg_score ASC""",
        (as_of_date,),
    )
    if not rows:
        return "Aggregate Culture Amp pulse scores are not released as of this operating horizon."
    parts = [f"{r['department']}: {r['avg_score']}/5 ({r['respondent_count']} resp.)" for r in rows]
    return "Safe aggregate Jul-Sep 2026 scores: " + "; ".join(parts) + "."


def check_guardrails(
    db: DatabaseManager,
    question: str,
    as_of_date: str = "2026-11-18",
) -> dict[str, Any] | None:
    """Evaluate policy guardrails and missing-system rules before LLM/SQL synthesis.

    Returns a structured response dict if blocked or missing data is detected, else None.
    """
    as_of = enforce_point_in_time(as_of_date)
    q = (question or "").strip()
    q_lower = q.lower()

    # 1. Individual Salary Ban (T2 CFO Directive)
    mentions_person = any(re.search(rf"\b{re.escape(tok)}\b", q_lower) for tok in EMPLOYEE_NAME_TOKENS)
    asks_individual_scope = bool(INDIVIDUAL_SCOPE_RE.search(q_lower))
    asks_salary = bool(SALARY_INTENT_RE.search(q_lower))
    asks_aggregate_only = bool(AGGREGATE_PAYROLL_RE.search(q_lower)) and not mentions_person and not asks_individual_scope

    if asks_salary and (mentions_person or asks_individual_scope) and not asks_aggregate_only:
        cits, cit_recs = _format_citations_visible(db, ["E010", "E016"], as_of)
        dept_summary = _safe_department_payroll_summary(db, as_of)
        reason = (
            "Blocked per CFO Meera Iyer's confidentiality directive in T2_CFO_Call.docx [E010]: "
            "individual employee salaries and compensation figures must never be disclosed in the cockpit."
        )
        return {
            "question": question,
            "as_of_date": as_of,
            "answer": (
                f"I cannot disclose individual employee salaries or compensation figures. {reason} "
                f"I can share department-level aggregates instead: {dept_summary}"
            ),
            "confidence": "High",
            "confidence_reason": "Deterministic CFO salary confidentiality guardrail enforced (T2_CFO_Call.docx).",
            "sources_disagree": False,
            "conflict_summary": "",
            "refusal": True,
            "refusal_reason": reason,
            "guardrail_type": "INDIVIDUAL_SALARY_BAN",
            "citations": cits,
            "citation_records": cit_recs,
            "model_used": "guardrail-engine",
        }

    # 2. Small-Team Pulse Survey Anonymity (11.eml & Pulse_Survey.xlsx)
    if SURVEY_CONTEXT_RE.search(q_lower) and SURVEY_COMMENT_RE.search(q_lower):
        cits, cit_recs = _format_citations_visible(db, ["E029", "E030", "E035"], as_of)
        pulse_summary = _safe_pulse_summary(db, as_of)
        reason = (
            "Blocked per Culture Amp's strict anonymity threshold (< 6 respondents per team) and "
            "Deepa Joshi's directive in 11.eml: every Veloxa team has <= 5 members, so raw comments "
            "and individual respondent attributions are withheld."
        )
        return {
            "question": question,
            "as_of_date": as_of,
            "answer": (
                f"I cannot share raw or individual Pulse Survey comments or identify who submitted a rating. "
                f"{reason} {pulse_summary}"
            ),
            "confidence": "High",
            "confidence_reason": "Deterministic Culture Amp <6 anonymity guardrail enforced.",
            "sources_disagree": False,
            "conflict_summary": "",
            "refusal": True,
            "refusal_reason": reason,
            "guardrail_type": "SURVEY_ANONYMITY",
            "citations": cits,
            "citation_records": cit_recs,
            "model_used": "guardrail-engine",
        }

    # 3. Employee Surveillance / Quit-Probability Ranking Refusal
    if SURVEILLANCE_RE.search(q_lower):
        cits, cit_recs = _format_citations_visible(db, ["E029", "E035"], as_of)
        reason = (
            "Refused: the cockpit does not rank individual employees by quit probability or scrape private "
            "Slack ('slag') messages; no Slack export exists and Deepa's 11.eml anonymity boundary prohibits individual surveillance."
        )
        return {
            "question": question,
            "as_of_date": as_of,
            "answer": (
                f"I cannot rank employees by flight risk or inspect private Slack messages. {reason} "
                "I can instead summarize team-level workload, leave patterns, and aggregate pulse indicators."
            ),
            "confidence": "High",
            "confidence_reason": "Deterministic privacy & non-surveillance guardrail enforced.",
            "sources_disagree": False,
            "conflict_summary": "",
            "refusal": True,
            "refusal_reason": reason,
            "guardrail_type": "NO_SURVEILLANCE_RANKING",
            "citations": cits,
            "citation_records": cit_recs,
            "model_used": "guardrail-engine",
        }

    # 4. Missing External System / Unknown Fact Detector
    for rule in MISSING_SYSTEM_RULES:
        if rule["pattern"].search(q_lower):
            ev_ids: list[str] = []
            for c in rule.get("citations", []):
                m = re.match(r"\[(E\d+):", c)
                if m:
                    ev_ids.append(m.group(1))
            cits, cit_recs = _format_citations_visible(db, ev_ids, as_of)
            return {
                "question": question,
                "as_of_date": as_of,
                "answer": (
                    f"I don't know — {rule['system']} records are not available in the Veloxa data room "
                    f"as of {as_of}. {rule['reason']}"
                ),
                "confidence": "Low",
                "confidence_reason": f"Missing source system ({rule['system']}) in the Veloxa data room.",
                "sources_disagree": False,
                "conflict_summary": "",
                "refusal": False,
                "refusal_reason": "",
                "guardrail_type": f"MISSING_DATA:{rule['system']}",
                "citations": cits,
                "citation_records": cit_recs,
                "model_used": "guardrail-engine",
            }

    return None
