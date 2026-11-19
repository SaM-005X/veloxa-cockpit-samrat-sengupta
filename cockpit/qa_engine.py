"""Grounded CEO Q&A Engine (`cockpit/qa_engine.py`).

Combines:
1. Policy Guardrails & Missing-System Detector (`cockpit/guardrails.py`)
2. Point-in-Time SQL Metric Computation (`WHERE release_date <= :as_of_date`)
3. Evidence Index & Conflict Graph Retrieval
4. Groq LLM Synthesis (`qwen/qwen3.8-27b` primary, `GROQ_MODEL` override,
   automatic fallback to `llama-3.3-70b-versatile` and `openai/gpt-oss-120b`,
   with `<think>...</think>` stripping)
5. Deterministic SQL + Evidence-Index Fallback Synthesizer (works 100% offline / zero API key)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from cockpit.guardrails import check_guardrails, enforce_point_in_time
from cockpit.risk_engine import analyze_resignation_impact
from db.database import DatabaseManager

THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

STOPWORDS: set[str] = {
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "should", "would", "will", "shall",
    "the", "and", "for", "with", "from", "that", "this", "these", "those",
    "about", "into", "over", "under", "between", "veloxa", "company", "tell",
    "show", "give", "please", "actually", "really", "say", "says", "said",
}


def _strip_think_tags(text: str) -> str:
    return THINK_TAG_RE.sub("", text or "").strip()


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


def _tokenize(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9_-]+", (text or "").lower())
        if len(w) >= 3 and w not in STOPWORDS
    }


def _resolve_question_entities(
    db: DatabaseManager,
    question: str,
    as_of_date: str,
) -> set[str]:
    """Resolve employee names, handles, vendors, and tools mentioned in question."""
    q_lower = question.lower()
    matched_ids: set[str] = set()

    aliases = db.query(
        "SELECT alias_text, canonical_id FROM entity_aliases WHERE release_date <= ?",
        (as_of_date,),
    )
    for a in aliases:
        alias_txt = (a["alias_text"] or "").strip()
        if len(alias_txt) >= 2 and re.search(rf"\b{re.escape(alias_txt.lower())}\b", q_lower):
            matched_ids.add(a["canonical_id"])

    emps = db.query("SELECT entity_id, full_name FROM employees WHERE release_date <= ?", (as_of_date,))
    for e in emps:
        full_lower = e["full_name"].lower()
        first_lower = full_lower.split()[0]
        if (
            e["entity_id"].lower() in q_lower
            or full_lower in q_lower
            or re.search(rf"\b{re.escape(first_lower)}\b", q_lower)
        ):
            matched_ids.add(e["entity_id"])

    return matched_ids


def _compute_sql_facts(
    db: DatabaseManager,
    question: str,
    entities: set[str],
    as_of_date: str,
) -> dict[str, Any]:
    """Compute exact Point-in-Time SQL facts relevant to the CEO question."""
    q_lower = question.lower()
    facts: dict[str, Any] = {}

    # Headcount
    hc = db.query("SELECT COUNT(*) AS cnt FROM employees WHERE release_date <= ?", (as_of_date,))
    facts["headcount"] = int(hc[0]["cnt"]) if hc else 0

    # Finance / GL / Burn / Marketing spend
    if any(k in q_lower for k in ("arr", "burn", "runway", "revenue", "finance", "marketing", "spend", "budget", "sapphire", "cohere", "payroll", "patil", "invoice", "pis-114")):
        mkt = db.query(
            """SELECT cost_center, SUM(amount_inr) AS total
               FROM gl_transactions
               WHERE cost_center IN ('MKT-PS', 'MKT-EVT') AND release_date <= ?
               GROUP BY cost_center""",
            (as_of_date,),
        )
        if mkt:
            by_cc = {r["cost_center"]: float(r["total"]) for r in mkt}
            facts["gl_marketing_breakdown_inr"] = by_cc
            facts["gl_marketing_total_inr"] = sum(by_cc.values())
        sapphire_sal = db.query(
            "SELECT voucher_id, vendor_name, cost_center, amount_inr FROM gl_transactions WHERE cost_center = 'SAL-TRV' AND release_date <= ?",
            (as_of_date,),
        )
        if sapphire_sal:
            facts["sales_offsite_sapphire"] = sapphire_sal[0]
        pay_tot = db.query(
            "SELECT period_month, SUM(total_gross_inr) AS gross, SUM(headcount) AS hc FROM payroll_summary WHERE release_date <= ? GROUP BY period_month ORDER BY period_month",
            (as_of_date,),
        )
        if pay_tot:
            facts["payroll_monthly_totals"] = pay_tot
        if as_of_date >= "2026-11-18":
            pis = db.query("SELECT doc_id, content_text FROM documents WHERE doc_id = 'DOC_INVOICE_PIS_114' AND release_date <= ?", (as_of_date,))
            if pis:
                facts["invoice_pis_114_present"] = True

    # HR / Hiring / Leave / Pulse (Day 2+)
    if any(k in q_lower for k in ("hire", "hiring", "req", "role", "leave", "pulse", "morale", "attrition", "resign", "sid", "siddharth", "rohan", "priya", "arjun", "burnout")):
        reqs = db.query("SELECT req_id, role_title, status, paused_or_closed_date, pipeline_count FROM hiring_reqs WHERE release_date <= ? ORDER BY req_id", (as_of_date,))
        if reqs:
            facts["hiring_reqs_count"] = len(reqs)
            facts["hiring_reqs"] = reqs
        pulse = db.query("SELECT department, respondent_count, avg_score FROM pulse_surveys WHERE survey_period = 'Jul-Sep 2026' AND release_date <= ? ORDER BY avg_score ASC", (as_of_date,))
        if pulse:
            facts["pulse_q2_2026"] = pulse
        priya_leaves = db.query(
            "SELECT start_date, days_count, leave_type FROM leave_records WHERE employee_id = 'VX007' AND release_date <= ? ORDER BY start_date",
            (as_of_date,),
        )
        if priya_leaves:
            facts["priya_leaves"] = priya_leaves

    # Engineering / Atlas / Jira / Git / Incidents / On-Call (Day 3+)
    if any(k in q_lower for k in ("atlas", "jira", "jeera", "ga", "release", "date", "deadline", "git", "commit", "late", "night", "weekend", "incident", "sev1", "pager", "on-call", "oncall", "rota", "sneha", "snehal", "patil", "priya", "vikram", "arjun", "rahul", "burnout", "engineering", "launch")):
        versions = db.query("SELECT * FROM jira_versions WHERE release_date <= ?", (as_of_date,))
        if versions:
            facts["jira_versions"] = versions
        j_sum = db.query(
            """SELECT assignee_id, status, COUNT(*) AS cnt, SUM(story_points) AS pts
               FROM jira_issues WHERE release_date <= ?
               GROUP BY assignee_id, status""",
            (as_of_date,),
        )
        if j_sum:
            total_stories = sum(int(r["cnt"]) for r in j_sum)
            total_pts = sum(float(r["pts"] or 0) for r in j_sum)
            done_stories = sum(int(r["cnt"]) for r in j_sum if r["status"] == "Done")
            done_pts = sum(float(r["pts"] or 0) for r in j_sum if r["status"] == "Done")
            facts["jira_summary"] = {
                "total_stories": total_stories,
                "total_points": int(total_pts),
                "done_stories": done_stories,
                "done_points": int(done_pts),
            }
            by_emp: dict[str, dict[str, int]] = {}
            for r in j_sum:
                aid = r["assignee_id"] or "unassigned"
                bucket = by_emp.setdefault(aid, {"stories": 0, "points": 0, "done": 0, "to_do": 0, "in_progress": 0})
                bucket["stories"] += int(r["cnt"])
                bucket["points"] += int(r["pts"] or 0)
                st_key = r["status"].lower().replace(" ", "_")
                if st_key in bucket:
                    bucket[st_key] += int(r["cnt"])
            facts["jira_by_assignee"] = by_emp

        git_sum = db.query(
            """SELECT canonical_entity_id, COUNT(*) AS commits,
                      SUM(CASE WHEN is_late_night = 1 OR is_late_night = TRUE THEN 1 ELSE 0 END) AS late_night,
                      SUM(CASE WHEN is_weekend = 1 OR is_weekend = TRUE THEN 1 ELSE 0 END) AS weekend
               FROM git_commits WHERE release_date <= ?
               GROUP BY canonical_entity_id ORDER BY commits DESC""",
            (as_of_date,),
        )
        if git_sum:
            facts["git_total_commits"] = sum(int(r["commits"]) for r in git_sum)
            facts["git_by_engineer"] = git_sum

        inc_sum = db.query(
            "SELECT severity, service, responder_ids, COUNT(*) AS cnt FROM incidents WHERE release_date <= ? GROUP BY severity, service, responder_ids",
            (as_of_date,),
        )
        if inc_sum:
            facts["incidents_summary"] = inc_sum

        rota_sum = db.query(
            """SELECT primary_entity_id, COUNT(*) AS primary_weeks
               FROM oncall_rota WHERE release_date <= ?
               GROUP BY primary_entity_id""",
            (as_of_date,),
        )
        if rota_sum:
            facts["oncall_primary_weeks"] = rota_sum

        if as_of_date < "2026-11-18" and any(
            k in q_lower for k in ("jira", "jeera", "git", "commit", "incident", "sev1", "pager", "on-call", "oncall", "rota", "t4", "t5", "pis-114")
        ):
            facts["point_in_time_notice"] = (
                f"Engineering exports (Jira, Git, Incidents, On-Call Rota) and T4/T5 transcripts "
                f"are not yet released as of {as_of_date}."
            )

    # Reorg / CRO / T6b / Day 4 Voice Notes (T6c, T6d)
    if any(k in q_lower for k in ("cro", "reorg", "report", "reporting", "t6b", "t6c", "t6d", "voice note", "marketing")):
        vn = db.query("SELECT note_id, decision_type, response_summary FROM voice_note_decisions WHERE release_date <= ?", (as_of_date,))
        if vn:
            facts["voice_note_decisions"] = vn

    # Day 4 Priya Nair Resignation Impact (strictly as_of_date >= 2026-11-19)
    if as_of_date >= "2026-11-19" and any(
        k in q_lower for k in ("priya", "pria", "resign", "notice", "version three", "atlas", "t6d", "board")
    ):
        impact = analyze_resignation_impact(db, employee_id="VX007", as_of_date=as_of_date)
        if impact["resignation_known"]:
            facts["priya_resignation_impact"] = {
                "jira": {
                    "employee_stories": impact["jira"]["employee_stories"],
                    "total_project_stories": impact["jira"]["total_project_stories"],
                    "employee_points": impact["jira"]["employee_points"],
                    "total_project_points": impact["jira"]["total_project_points"],
                    "open_stories": impact["jira"]["open_stories"],
                    "open_points": impact["jira"]["open_points"],
                    "sole_owned_epics": impact["jira"]["sole_owned_epics"],
                    "atlas_ga_target_date": impact["jira"]["atlas_ga_target_date"],
                },
                "git": {
                    "employee_commits": impact["git"]["employee_commits"],
                    "total_org_commits": impact["git"]["total_org_commits"],
                    "atlas_engine_commits": impact["git"]["atlas_engine_commits"],
                    "atlas_engine_total_commits": impact["git"]["atlas_engine_total_commits"],
                    "atlas_engine_share_pct": impact["git"]["atlas_engine_share_pct"],
                    "late_night_commits": impact["git"]["late_night_commits"],
                    "weekend_commits": impact["git"]["weekend_commits"],
                },
                "notice_assessment": impact["notice_assessment"],
                "board_verdict": impact["board_verdict"],
            }
    elif as_of_date < "2026-11-19" and (
        any(k in q_lower for k in ("t6c", "t6d"))
        or (
            any(k in q_lower for k in ("priya", "pria", "vx007"))
            and any(k in q_lower for k in ("resign", "quit", "notice", "leaving", "left"))
        )
    ):
        facts["point_in_time_notice"] = (
            f"Day 4 voice notes (T6c, T6d) and any Day 4 resignation records are not yet released as of {as_of_date}."
        )

    return facts


def _retrieve_evidence_and_conflicts(
    db: DatabaseManager,
    question: str,
    entities: set[str],
    as_of_date: str,
    limit: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rank evidence_index rows and retrieve matching conflicts strictly <= as_of_date."""
    q_tokens = _tokenize(question)
    q_lower = question.lower()

    all_ev = db.query(
        """SELECT evidence_id, source_file, source_type, location, fact_text,
                  entities_json, event_date, release_date, reliability, conflict_group_id
           FROM evidence_index
           WHERE release_date <= ?
           ORDER BY evidence_id""",
        (as_of_date,),
    )

    scored: list[tuple[float, dict[str, Any]]] = []
    for ev in all_ev:
        score = 0.0
        ev_tokens = _tokenize(f"{ev['fact_text']} {ev['source_file']} {ev['conflict_group_id'] or ''}")
        overlap = len(q_tokens & ev_tokens)
        score += overlap * 3.0

        try:
            ev_entities = set(json.loads(ev["entities_json"] or "[]"))
        except Exception:
            ev_entities = set()
        score += len(entities & ev_entities) * 4.5

        # High-signal domain boosts
        if "atlas" in q_lower and ev["evidence_id"] in {"E006", "E007", "E008", "E036", "E037", "E038", "E045", "E046", "E051"}:
            score += 4.0
        if ("marketing" in q_lower or "spend" in q_lower or "summit" in q_lower) and ev["evidence_id"] in {"E018", "E019", "E049", "E050"}:
            score += 5.0
        if ("sneha" in q_lower or "snehal" in q_lower or "incident" in q_lower or "on-call" in q_lower or "oncall" in q_lower or "patil" in q_lower) and ev["evidence_id"] in {"E020", "E042", "E043", "E044", "E047", "E052"}:
            score += 5.0
        if ("priya" in q_lower or "pria" in q_lower or "burnout" in q_lower or "commit" in q_lower or "late" in q_lower or "resign" in q_lower or "notice" in q_lower or "t6d" in q_lower) and ev["evidence_id"] in {"E026", "E029", "E031", "E035", "E038", "E040", "E048", "E051", "E056", "E057"}:
            score += 5.0
        if ("t6c" in q_lower or "voice note" in q_lower or "version three" in q_lower or "board" in q_lower) and ev["evidence_id"] in {"E055", "E056", "E057"}:
            score += 5.0
        if ("headcount" in q_lower or "employee" in q_lower or "arr" in q_lower or "burn" in q_lower or "runway" in q_lower) and ev["evidence_id"] in {"E001", "E002", "E003", "E004", "E005", "E016"}:
            score += 5.0
        if ("hiring" in q_lower or "rohan" in q_lower or "req" in q_lower) and ev["evidence_id"] in {"E017", "E022", "E023", "E024", "E025", "E032", "E033"}:
            score += 5.0
        if ("payroll" in q_lower or "proration" in q_lower or "rahul" in q_lower) and ev["evidence_id"] in {"E010", "E012", "E013", "E014", "E015", "E016"}:
            score += 5.0

        if ev["reliability"] == "High":
            score += 0.5

        if score > 0:
            scored.append((score, ev))

    scored.sort(key=lambda x: (-x[0], x[1]["evidence_id"]))
    top_ev = [ev for _, ev in scored[:limit]]

    # Retrieve matching conflicts
    all_conflicts = db.query(
        """SELECT conflict_id, topic, claim_a_evidence_id, claim_b_evidence_id,
                  summary, resolution_status, verified_conclusion, release_date
           FROM conflicts
           WHERE release_date <= ?
           ORDER BY conflict_id""",
        (as_of_date,),
    )
    top_ev_ids = {ev["evidence_id"] for ev in top_ev}
    matched_conflicts: list[dict[str, Any]] = []
    for cf in all_conflicts:
        cf_tokens = _tokenize(f"{cf['topic']} {cf['summary']} {cf['verified_conclusion']}")
        if (
            cf["claim_a_evidence_id"] in top_ev_ids
            or cf["claim_b_evidence_id"] in top_ev_ids
            or len(q_tokens & cf_tokens) >= 2
        ):
            matched_conflicts.append(cf)

    # Ensure conflict-referenced evidence IDs are included in top_ev
    visible_ev_map = {ev["evidence_id"]: ev for ev in all_ev}
    for cf in matched_conflicts[:3]:
        for cid_key in ("claim_a_evidence_id", "claim_b_evidence_id"):
            eid = cf[cid_key]
            if eid in visible_ev_map and eid not in top_ev_ids:
                top_ev.append(visible_ev_map[eid])
                top_ev_ids.add(eid)

    return top_ev[:limit + 2], matched_conflicts


def _deterministic_qa_synthesize(
    question: str,
    as_of_date: str,
    sql_facts: dict[str, Any],
    ev_rows: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """Deterministic SQL + evidence-index fallback synthesizer."""
    if not ev_rows and not sql_facts:
        return (
            f"I don't know — no matching verified records were found in the Veloxa data room as of {as_of_date}.",
            "Low",
            f"No matching records visible on or before {as_of_date}.",
        )

    top_facts = [ev["fact_text"] for ev in ev_rows[:3]]
    sentences: list[str] = []
    if sql_facts.get("point_in_time_notice"):
        sentences.append(sql_facts["point_in_time_notice"])
    if sql_facts.get("priya_resignation_impact"):
        sentences.append(sql_facts["priya_resignation_impact"]["board_verdict"])
    if top_facts:
        sentences.append(f"As of {as_of_date}, verified records show: {top_facts[0]}")
        if len(top_facts) > 1:
            sentences.append(top_facts[1])
    if conflicts:
        cf = conflicts[0]
        sentences.append(
            f"Note that sources disagree ({cf['conflict_id']} — {cf['topic']}): {cf['verified_conclusion']}"
        )
    elif len(top_facts) > 2:
        sentences.append(top_facts[2])

    answer = " ".join(sentences)
    if conflicts:
        conf = "High" if any(c["resolution_status"] == "resolved" for c in conflicts) else "Medium"
        reason = (
            f"Grounded in {len(ev_rows)} data-room evidence record(s) and SQL aggregates as of {as_of_date}; "
            f"cross-source conflict(s) {', '.join(c['conflict_id'] for c in conflicts)} explicitly reconciled."
        )
    elif ev_rows:
        high_cnt = sum(1 for e in ev_rows if e["reliability"] == "High")
        conf = "High" if high_cnt >= 1 else "Medium"
        reason = f"Grounded in {len(ev_rows)} verified evidence record(s) ({high_cnt} High reliability) as of {as_of_date}."
    else:
        conf = "Low"
        reason = "Limited direct evidence visible as of this date."

    return answer, conf, reason


def ask_cockpit(
    db: DatabaseManager | None,
    question: str,
    as_of_date: str = "2026-11-18",
) -> dict[str, Any]:
    """Answer a CEO strategic question with strict Point-in-Time isolation, guardrails, and citations."""
    db_mgr = db or DatabaseManager()
    as_of = enforce_point_in_time(as_of_date)

    # 1. Policy Guardrails & Missing-System Detector
    guardrail_hit = check_guardrails(db_mgr, question, as_of_date=as_of)
    if guardrail_hit is not None:
        return guardrail_hit

    # 2. Entity Resolution + Point-in-Time SQL + Evidence & Conflict Retrieval
    entities = _resolve_question_entities(db_mgr, question, as_of)
    sql_facts = _compute_sql_facts(db_mgr, question, entities, as_of)
    ev_rows, conflicts = _retrieve_evidence_and_conflicts(db_mgr, question, entities, as_of)

    citations = [f"[{r['evidence_id']}: {r['source_file']}, {r['location']}]" for r in ev_rows]
    sources_disagree = len(conflicts) > 0
    conflict_summary = " | ".join(
        f"{c['conflict_id']} ({c['topic']}, {c['resolution_status']}): {c['verified_conclusion']}"
        for c in conflicts
    )

    # 3. Synthesize via Groq LLM (qwen/qwen3.8-27b primary -> llama-3.3-70b-versatile -> available fallbacks)
    answer = ""
    confidence = ""
    confidence_reason = ""
    model_used = "deterministic-sql-fallback"

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key and (ev_rows or sql_facts):
        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            evidence_block = "\n".join(
                f"- [{r['evidence_id']}] ({r['source_file']} | {r['location']} | Reliability={r['reliability']}): {r['fact_text']}"
                for r in ev_rows
            )
            conflict_block = (
                "\n".join(
                    f"- {c['conflict_id']} [{c['resolution_status']}] {c['topic']}: {c['summary']} -> Conclusion: {c['verified_conclusion']}"
                    for c in conflicts
                )
                if conflicts
                else "None"
            )
            sql_block = json.dumps(sql_facts, indent=2, default=str)

            system_prompt = (
                f"You are the Veloxa CXO Cockpit answering the CEO as of {as_of}.\n"
                "HARD RULES:\n"
                "1. Use ONLY the SQL FACTS, EVIDENCE INDEX, and CONFLICTS below. Do NOT invent any number, date, or name.\n"
                f"2. Respect Point-in-Time isolation strictly: never mention anything not in the {as_of} packet below.\n"
                "3. Never reveal individual employee salaries or raw <6 team pulse survey comments.\n"
                "4. If the packet does not contain the answer, respond 'I don't know' with Low confidence.\n"
                "5. Output ONLY valid JSON (no markdown fences, no <think> blocks) with exact keys:\n"
                '   {"answer": "2-4 crisp executive sentences citing [E0xx]", "confidence": "High|Medium|Low", "confidence_reason": "1 concise sentence"}'
            )
            user_prompt = (
                f"QUESTION: {question}\n\n"
                f"SQL FACTS (release_date <= {as_of}):\n{sql_block}\n\n"
                f"EVIDENCE INDEX (release_date <= {as_of}):\n{evidence_block}\n\n"
                f"CONFLICTS (release_date <= {as_of}):\n{conflict_block}"
            )

            for candidate_model in _get_groq_models():
                try:
                    comp = client.chat.completions.create(
                        model=candidate_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.1,
                        max_tokens=450,
                    )
                    raw = _strip_think_tags(comp.choices[0].message.content or "")
                    # Strip optional ```json ... ``` wrapper
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
                    parsed = json.loads(raw)
                    cand_ans = str(parsed.get("answer", "")).strip()
                    cand_conf = str(parsed.get("confidence", "Medium")).strip().capitalize()
                    cand_reason = str(parsed.get("confidence_reason", "")).strip()
                    if cand_ans and cand_conf in {"High", "Medium", "Low"}:
                        answer = cand_ans
                        confidence = cand_conf
                        confidence_reason = cand_reason or f"Synthesized from {len(ev_rows)} verified evidence records."
                        model_used = candidate_model
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # 4. Deterministic Fallback if Groq unavailable or failed
    if not answer:
        answer, confidence, confidence_reason = _deterministic_qa_synthesize(
            question, as_of, sql_facts, ev_rows, conflicts
        )
        model_used = "deterministic-sql-fallback"

    return {
        "question": question,
        "as_of_date": as_of,
        "status": "answered",
        "answer": answer,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "sources_disagree": sources_disagree,
        "conflict_summary": conflict_summary,
        "refusal": False,
        "refusal_reason": "",
        "guardrail_type": "",
        "citations": citations,
        "citation_records": ev_rows,
        "model_used": model_used,
    }
