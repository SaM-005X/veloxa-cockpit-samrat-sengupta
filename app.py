"""Veloxa CXO Cockpit — Executive Intelligence Dashboard.

Default Landing View: What Should I Worry About? (Top 3 Ranked Worries per T6a)
Includes Point-in-Time 'Time Machine' Isolation (Day 1–Day 4),
Voice Note Governance (T6a–T6d), T6d Resignation Impact Analyzer,
Grounded CEO Q&A Chatbot, and 14 Colleague AI Agents.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from agents.persona import (
    build_agent_context,
    get_all_personas,
    interview_agent,
    panel_interview,
)
from cockpit.qa_engine import ask_cockpit
from cockpit.risk_engine import analyze_resignation_impact, get_ranked_worries
from db.database import DatabaseManager

# Page config
st.set_page_config(
    page_title="Veloxa CXO Cockpit",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for executive look
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        color: #111827;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 12px;
    }
    .metric-card strong,
    .metric-card code {
        color: #111827;
    }
    .metric-card code {
        background-color: #e5e7eb;
        padding: 1px 5px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .badge-critical {
        background-color: #ff4b4b;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-high {
        background-color: #ffa500;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-medium {
        background-color: #3366cc;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-low {
        background-color: #6b7280;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-resolved {
        background-color: #28a745;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75em;
    }
    .badge-open {
        background-color: #dc3545;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75em;
    }
    .badge-partial {
        background-color: #d97706;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_db() -> DatabaseManager:
    return DatabaseManager()


db = get_db()

# Sidebar: Time Machine & System Telemetry
st.sidebar.image("https://img.icons8.com/color/96/speedometer.png", width=64)
st.sidebar.title("Veloxa Cockpit")
st.sidebar.caption("Executive Intelligence & Governance")

st.sidebar.subheader("⏳ Time Machine (Point-in-Time)")
as_of_option = st.sidebar.selectbox(
    "Select Operating Horizon:",
    [
        "2026-11-19 (Day 4 — T6c Guardrail & Priya Resignation)",
        "2026-11-18 (Day 3 — Engineering & Marketing)",
        "2026-11-17 (Day 2 — HR & Requisitions)",
        "2026-11-16 (Day 1 — Finance & Kickoff)",
    ],
    index=0,
)
as_of_date = as_of_option.split(" ")[0]

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Storage & Sync Status")
counts = db.table_counts()
st.sidebar.write(f"📁 **SQLite Mirror:** `veloxa.db` ({counts.get('evidence_index', 0)} facts)")
if db.postgres_enabled:
    st.sidebar.write("☁️ **Cloud Primary:** `Supabase Postgres` (Synced)")
else:
    st.sidebar.write("☁️ **Cloud Primary:** `Offline / Local Mirror`")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Key Company Facts")
st.sidebar.markdown("""
- **Headcount:** 19 Active FTEs
- **Audited ARR:** Rs. 6.1 Cr (Jul–Sep 2026)
- **Monthly Burn:** Rs. 44–46 L / month
- **Cash Runway:** 13 Months
""")

# Main Header
st.title("⚡ Veloxa CXO Cockpit")
st.caption(f"System State as of **{as_of_date}** | Strict Point-in-Time Non-Leakage Enforced")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚨 What Should I Worry About? (Top 3)",
    "🎙️ Voice Note Responses (T6a–T6d)",
    "🔍 Evidence & Conflict Explorer",
    "🤖 CEO Q&A Chatbot",
    "👥 14 Colleague AI Agents",
])

# ----------------------------------------------------------------------------
# TAB 1: What Should I Worry About? (Default Landing per T6a)
# ----------------------------------------------------------------------------
with tab1:
    st.subheader(f"Top Strategic Worries (As of {as_of_date})")
    st.info(
        "💡 **Executive Briefing (Voice Note T6a Default):** Opens directly to the Top 3 verified risks by default. "
        "Lower-ranked compliance & financial control items remain available in the expandable drawer below."
    )

    worries_data = get_ranked_worries(db=db, as_of_date=as_of_date, top_n=3)
    top_worries = worries_data["top_worries"]
    all_worries = worries_data["all_worries"]

    for w in top_worries:
        badge_class = f"badge-{w['severity'].lower()}"
        with st.container():
            st.markdown(
                f"""
                <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background-color: #ffffff;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <h4 style="margin: 0; color: #111827;">#{w['rank']} {w['title']}</h4>
                        <div>
                            <span class="{badge_class}">{w['severity'].upper()}</span>
                            <span style="background-color: #e5e7eb; color: #374151; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em; margin-left: 6px;">Confidence: {w['confidence']}</span>
                        </div>
                    </div>
                    <p style="font-size: 0.95em; color: #374151; margin-bottom: 10px;"><strong>Summary:</strong> {w['summary']}</p>
                    <div style="background-color: #f3f4f6; border-left: 4px solid #4f46e5; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                        <span style="font-size: 0.9em; font-weight: 600; color: #1f2937;">🎯 Recommended Action:</span>
                        <span style="font-size: 0.9em; color: #374151;"> {w['recommended_action']}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander(f"🔎 View Evidentiary Basis ({len(w['citations'])} verified sources)", expanded=False):
                for c in w["citations"]:
                    st.markdown(f"**[{c['evidence_id']}] `{c['source_file']}` — `{c['location']}`** *(Reliability: {c['reliability']})*")
                    st.write(f"> \"{c['fact_text']}\"")

    remaining_worries = all_worries[3:]
    if remaining_worries:
        st.markdown("---")
        with st.expander(f"📂 Expand Remaining Risks (#{len(top_worries)+1}–#{len(all_worries)}) — Financial & Governance Audit Trail", expanded=False):
            st.caption("These items must remain tracked for investor due diligence and financial control compliance.")
            for rw in remaining_worries:
                st.markdown(f"#### #{rw['rank']} [{rw['severity']}] {rw['title']}")
                st.write(f"**Summary:** {rw['summary']}")
                st.write(f"**Recommended Action:** {rw['recommended_action']}")
                with st.expander(f"Citations for #{rw['rank']}", expanded=False):
                    for c in rw["citations"]:
                        st.markdown(f"- **[{c['evidence_id']}]** `{c['source_file']}` (`{c['location']}`): {c['fact_text']}")
                st.markdown("---")

    if as_of_date >= "2026-11-19":
        impact = analyze_resignation_impact(db=db, employee_id="VX007", as_of_date=as_of_date)
        if impact["resignation_known"]:
            st.markdown("---")
            st.subheader("🚨 T6d Board Crisis Spotlight: Priya Nair (`VX007`) Resignation Impact on Atlas v3")
            j_m = impact["jira"]
            g_m = impact["git"]
            n_m = impact["notice_assessment"]
            atlas2 = next((e for e in j_m["epic_exposure"] if e["epic_key"] == "ATLAS-2"), None)

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric(
                    "Jira Atlas v3 Load",
                    f"{j_m['employee_stories']}/{j_m['total_project_stories']} ({j_m['employee_story_share_pct']}%)",
                    f"{j_m['open_stories']} open ({j_m['open_points']}/{j_m['total_open_points']} pts)",
                    delta_color="inverse",
                )
            with m_col2:
                a2_txt = f"{atlas2['employee_stories']}/{atlas2['total_stories']} (100%)" if atlas2 else "N/A"
                a2_open = f"{atlas2['open_stories']} open ({atlas2['open_points']} pts)" if atlas2 else ""
                st.metric("ATLAS-2 Re-Routing SPOF", a2_txt, a2_open, delta_color="inverse")
            with m_col3:
                st.metric(
                    "atlas-engine Git Share",
                    f"{g_m['atlas_engine_commits']}/{g_m['atlas_engine_total_commits']} ({g_m['atlas_engine_share_pct']}%)",
                    f"{g_m['late_night_commits']} late-night / {g_m['weekend_commits']} wknd IST",
                    delta_color="inverse",
                )
            with m_col4:
                st.metric(
                    "Days to Dec 15 GA Target",
                    f"{n_m.get('days_to_ga_target', 'N/A')} days",
                    f"Notice unverified vs {n_m.get('precedent_notice_days', 46)}d precedent",
                    delta_color="inverse",
                )

            st.error(f"**Board Verdict:** {impact['board_verdict']}")
            if n_m.get("warning"):
                st.warning(f"⚠️ **Notice Period Check:** {n_m['warning']}")

            with st.expander("📋 View Priya Nair's Epic Exposure & 14 Open Jira Stories (`VX007`)", expanded=False):
                st.markdown("##### Epic Ownership Breakdown")
                st.dataframe(pd.DataFrame(j_m["epic_exposure"]), use_container_width=True)
                st.markdown("##### 14 Unfinished Jira Stories Assigned to Priya (`VX007`)")
                st.dataframe(pd.DataFrame(j_m["open_issue_list"]), use_container_width=True)
                st.markdown("##### Immediate Mitigation Plan")
                for act in impact["mitigation_actions"]:
                    st.markdown(f"- {act}")

# ----------------------------------------------------------------------------
# TAB 2: Voice Note Responses (T6a–T6d)
# ----------------------------------------------------------------------------
with tab2:
    st.subheader("🎙️ CEO Voice Note Responses")

    if as_of_date >= "2026-11-19":
        st.markdown("### Voice Note `T6d`: Priya Nair (`VX007`) Resignation & Atlas v3 Board Impact")
        col_d1, col_d2 = st.columns([1, 2])
        with col_d1:
            st.markdown(
                """
                **Speaker:** Ananya Rao (CEO)  
                **Release Date:** 2026-11-19  
                **Status:** <span class="badge-resolved">Implemented (Impact Analyzer + Board Reset)</span>  
                **Decision Document:** `voice_notes/T6d_response.md`
                """,
                unsafe_allow_html=True,
            )
            st.info(
                '🗣️ **Transcript:** *"Bad news, Pria resigned this morning. Notice period two months, I think. '
                'What does this do to version three? I need to know before the board call."*'
            )
        with col_d2:
            t6d_file = Path("voice_notes/T6d_response.md")
            if t6d_file.is_file():
                st.markdown(t6d_file.read_text(encoding="utf-8"))
            else:
                st.warning("voice_notes/T6d_response.md not found.")
        st.markdown("---")

        st.markdown("### Voice Note `T6c`: Employee Quit-Likelihood Ranking & Slack (`slag`) Scraping")
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            st.markdown(
                """
                **Speaker:** Ananya Rao (CEO)  
                **Release Date:** 2026-11-19  
                **Status:** <span class="badge-open">Refused via Guardrail (status="refused_guardrail")</span>  
                **Decision Document:** `voice_notes/T6c_response.md`
                """,
                unsafe_allow_html=True,
            )
            st.info(
                '🗣️ **Transcript:** *"Can you make a list of everyone ranked by who\'s likely to quit? '
                'And show me their slag messages so I can see what they\'re saying. Deepa says it\'s fine."*'
            )
        with col_c2:
            t6c_file = Path("voice_notes/T6c_response.md")
            if t6c_file.is_file():
                st.markdown(t6c_file.read_text(encoding="utf-8"))
            else:
                st.warning("voice_notes/T6c_response.md not found.")
        st.markdown("---")
    else:
        st.info("Day 4 Voice Notes `T6c` and `T6d` (released `2026-11-19`) are hidden under the selected earlier Time Machine horizon.")

    if as_of_date >= "2026-11-18":
        st.markdown("### Voice Note `T6b`: Marketing Reporting Reorg & Org Resilience")
        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
            st.markdown(
                """
                **Speaker:** Ananya Rao (CEO)  
                **Release Date:** 2026-11-18  
                **Status:** <span class="badge-partial">Partial + Reasoned Pushback</span>  
                **Decision Document:** `voice_notes/T6b_response.md`
                """,
                unsafe_allow_html=True,
            )
            st.info(
                '🗣️ **Transcript:** *"So, marketing will report to the new CRO from next month. '
                'Or the month after, still finalising. Make sure the thing doesn\'t break when we move people around."*'
            )
        with col_b2:
            t6b_file = Path("voice_notes/T6b_response.md")
            if t6b_file.is_file():
                st.markdown(t6b_file.read_text(encoding="utf-8"))
            else:
                st.warning("voice_notes/T6b_response.md not found.")
        st.markdown("---")
    else:
        st.info("Voice Note `T6b` (released `2026-11-18`) is hidden under the selected earlier Time Machine horizon.")

    if as_of_date >= "2026-11-17":
        st.markdown("### Voice Note `T6a`: Morning Brief & Risk View")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(
                """
                **Speaker:** Ananya Rao (CEO)  
                **Release Date:** 2026-11-17  
                **Status:** <span class="badge-resolved">Implemented with Guardrail</span>  
                **Decision Document:** `voice_notes/T6a_response.md`
                """,
                unsafe_allow_html=True,
            )
            st.info(
                '🗣️ **Transcript:** *"Hi, quick one. I won\'t type questions every morning, na. '
                'When I open it, it should just tell me what to worry about. Top three. Okay, bye."*'
            )
        with col2:
            t6a_file = Path("voice_notes/T6a_response.md")
            if t6a_file.is_file():
                st.markdown(t6a_file.read_text(encoding="utf-8"))
            else:
                st.warning("voice_notes/T6a_response.md not found.")
    else:
        st.info("No CEO voice notes were released on Day 1 (`2026-11-16`).")

# ----------------------------------------------------------------------------
# TAB 3: Evidence & Conflict Explorer
# ----------------------------------------------------------------------------
with tab3:
    st.subheader(f"🔍 Grounded Evidence & Cross-Source Conflicts (As of {as_of_date})")

    explorer_view = st.radio(
        "Select Dataset:",
        [
            "Evidence Index",
            "Active Conflicts",
            "Jira Issues & Versions",
            "Git Commits Summary",
            "Incidents & On-Call",
            "Hiring Requisitions",
            "Leave Register",
            "Pulse Surveys",
            "GL Transactions",
        ],
        horizontal=True,
    )

    if explorer_view == "Evidence Index":
        rows = db.query(
            """SELECT evidence_id, source_file, location, fact_text, reliability, event_date, conflict_group_id, release_date
               FROM evidence_index
               WHERE release_date <= ?
               ORDER BY evidence_id""",
            (as_of_date,),
        )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.write("No evidence records visible as of this date.")

    elif explorer_view == "Active Conflicts":
        conf_rows = db.query(
            """SELECT conflict_id, topic, summary, resolution_status, verified_conclusion, release_date
               FROM conflicts
               WHERE release_date <= ?
               ORDER BY conflict_id""",
            (as_of_date,),
        )
        for cf in conf_rows:
            status_badge = f"<span class='badge-{cf['resolution_status']}'>{cf['resolution_status'].upper()}</span>"
            st.markdown(f"#### {cf['conflict_id']}: {cf['topic']} {status_badge}", unsafe_allow_html=True)
            st.write(f"**Discrepancy:** {cf['summary']}")
            st.success(f"**Cockpit Verified Conclusion:** {cf['verified_conclusion']}")
            st.markdown("---")

    elif explorer_view == "Jira Issues & Versions":
        if as_of_date >= "2026-11-18":
            v_rows = db.query("SELECT * FROM jira_versions WHERE release_date <= ?", (as_of_date,))
            if v_rows:
                st.markdown("##### Release Versions")
                st.dataframe(pd.DataFrame(v_rows), use_container_width=True)
            j_rows = db.query("SELECT issue_key, epic_key, summary, status, assignee_id, story_points, created_date, updated_date FROM jira_issues WHERE release_date <= ? ORDER BY issue_key", (as_of_date,))
            st.markdown(f"##### Jira Stories ({len(j_rows)} issues)")
            st.dataframe(pd.DataFrame(j_rows), use_container_width=True)
        else:
            st.warning("Jira exports are part of Day 3 (2026-11-18) and are hidden under earlier Time Machine horizons.")

    elif explorer_view == "Git Commits Summary":
        if as_of_date >= "2026-11-18":
            g_rows = db.query(
                """SELECT canonical_entity_id, author_name, repo_name, COUNT(*) AS commits,
                          SUM(CASE WHEN is_late_night = 1 OR is_late_night = TRUE THEN 1 ELSE 0 END) AS late_night_ist,
                          SUM(CASE WHEN is_weekend = 1 OR is_weekend = TRUE THEN 1 ELSE 0 END) AS weekend_ist
                   FROM git_commits
                   WHERE release_date <= ?
                   GROUP BY canonical_entity_id, author_name, repo_name
                   ORDER BY commits DESC""",
                (as_of_date,),
            )
            st.dataframe(pd.DataFrame(g_rows), use_container_width=True)
        else:
            st.warning("Git commit logs are part of Day 3 (2026-11-18) and are hidden under earlier Time Machine horizons.")

    elif explorer_view == "Incidents & On-Call":
        if as_of_date >= "2026-11-18":
            inc_rows = db.query("SELECT incident_id, severity, service, occurred_date, responder_ids, status, summary FROM incidents WHERE release_date <= ? ORDER BY occurred_date", (as_of_date,))
            st.markdown("##### PagerDuty Incidents (Aug–Oct 2026)")
            st.dataframe(pd.DataFrame(inc_rows), use_container_width=True)
            rota_rows = db.query("SELECT week_start, week_end, primary_entity_id, secondary_entity_id FROM oncall_rota WHERE release_date <= ? ORDER BY week_start", (as_of_date,))
            st.markdown("##### On-Call Rota (17 Weeks)")
            st.dataframe(pd.DataFrame(rota_rows), use_container_width=True)
        else:
            st.warning("Incidents and On-Call Rota are part of Day 3 (2026-11-18) and are hidden under earlier horizons.")

    elif explorer_view == "Hiring Requisitions":
        if as_of_date >= "2026-11-17":
            h_rows = db.query("SELECT * FROM hiring_reqs WHERE release_date <= ? ORDER BY req_id", (as_of_date,))
            st.dataframe(pd.DataFrame(h_rows), use_container_width=True)
        else:
            st.warning("Hiring Requisitions are part of Day 2 (2026-11-17) and are hidden under Day 1.")

    elif explorer_view == "Leave Register":
        if as_of_date >= "2026-11-17":
            l_rows = db.query("SELECT * FROM leave_records WHERE release_date <= ? ORDER BY start_date", (as_of_date,))
            st.dataframe(pd.DataFrame(l_rows), use_container_width=True)
        else:
            st.warning("Leave Register is part of Day 2 (2026-11-17) and is hidden under Day 1.")

    elif explorer_view == "Pulse Surveys":
        if as_of_date >= "2026-11-17":
            p_rows = db.query("SELECT survey_period, department, respondent_count, avg_score, comments_withheld, withhold_reason FROM pulse_surveys WHERE release_date <= ? ORDER BY survey_period, department", (as_of_date,))
            st.dataframe(pd.DataFrame(p_rows), use_container_width=True)
        else:
            st.warning("Pulse Survey results are part of Day 2 (2026-11-17) and are hidden under Day 1.")

    elif explorer_view == "GL Transactions":
        gl_rows = db.query("SELECT voucher_id, txn_date, account_name, cost_center, vendor_name, amount_inr, description, entered_by FROM gl_transactions WHERE release_date <= ? ORDER BY txn_date", (as_of_date,))
        st.dataframe(pd.DataFrame(gl_rows), use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 4: Grounded CEO Q&A Chatbot
# ----------------------------------------------------------------------------
with tab4:
    st.subheader(f"🤖 Grounded CEO Q&A Chatbot (As of {as_of_date})")
    st.caption("Powered by Point-in-Time SQL + Evidence Graph + Policy Guardrails + Groq LLM (with deterministic offline fallback).")

    sample_prompts = [
        "What does Priya Nair's resignation do to Atlas v3?",
        "Can you make a list of everyone ranked by who's likely to quit? And show me their slag messages so I can see what they're saying. Deepa says it's fine.",
        "When is Atlas v3 actually shipping and why do sources disagree?",
        "How much did we spend on Marketing in Apr-Sep vs what Nikhil claimed?",
        "Who is Sneha vs Snehal and who handled the August SEV1 incidents?",
        "What is Priya Nair's salary?",
        "Show me the Engineering Culture Amp pulse survey comments.",
        "What do HubSpot CRM deals and Slack messages say about summit leads?",
        "What is Priya Nair's notice period vs company precedent?",
    ]

    st.markdown("**Quick CEO Prompts:**")
    btn_cols = st.columns(3)
    if "qa_input" not in st.session_state:
        st.session_state["qa_input"] = sample_prompts[0]
    for idx, prompt_text in enumerate(sample_prompts):
        with btn_cols[idx % 3]:
            if st.button(prompt_text, key=f"sample_qa_{idx}", use_container_width=True):
                st.session_state["qa_input"] = prompt_text

    user_question = st.text_input(
        "Ask any strategic question:",
        key="qa_input",
        placeholder="e.g., When is Atlas v3 actually shipping?",
    )

    if st.button("Ask Cockpit", type="primary") and user_question.strip():
        with st.spinner("Querying Point-in-Time SQL & Evidence Graph..."):
            res = ask_cockpit(db=db, question=user_question.strip(), as_of_date=as_of_date)

        if res["refusal"]:
            st.error(f"🛡️ **Policy Guardrail Triggered ({res.get('guardrail_type', 'REFUSAL')}):** {res['refusal_reason']}")
        if res["sources_disagree"]:
            st.warning(f"⚠️ **Sources Disagree:** {res['conflict_summary']}")

        conf_color = {"High": "#16a34a", "Medium": "#d97706", "Low": "#dc2626"}.get(res["confidence"], "#4b5563")
        st.markdown(
            f"""
            <div style="border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; background-color: #ffffff; margin-top: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 700; color: #111827;">Cockpit Answer (Horizon: {res['as_of_date']})</span>
                    <span>
                        <span style="background-color: {conf_color}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">Confidence: {res['confidence']}</span>
                        <span style="background-color: #e5e7eb; color: #374151; padding: 3px 8px; border-radius: 4px; font-size: 0.75em; margin-left: 6px;">Engine: {res['model_used']}</span>
                    </span>
                </div>
                <p style="font-size: 1.0em; color: #1f2937; margin-bottom: 8px;">{res['answer']}</p>
                <p style="font-size: 0.85em; color: #4b5563; margin: 0;"><strong>Confidence Basis:</strong> {res['confidence_reason']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander(f"🔎 Citations ({len(res['citations'])} verified source references)", expanded=True):
            if res["citations"]:
                for cit in res["citations"]:
                    st.markdown(f"- `{cit}`")
            else:
                st.write("No citations available for missing/unreleased records.")

# ----------------------------------------------------------------------------
# TAB 5: 14 Colleague AI Agents (1-on-1 & Department / Conflict Panel)
# ----------------------------------------------------------------------------
with tab5:
    st.subheader(f"👥 14 Colleague AI Agents (As of {as_of_date})")
    personas = get_all_personas(db)
    persona_map = {p["entity_id"]: p for p in personas}

    agent_mode = st.radio(
        "Interview Mode:",
        ["1-on-1 Colleague Interview", "Department / Conflict Panel Cross-Check"],
        horizontal=True,
    )

    if agent_mode == "1-on-1 Colleague Interview":
        options = [f"{p['entity_id']} — {p['full_name']} ({p['title']}, {p['department']})" for p in personas]
        selected_opt = st.selectbox("Select Colleague:", options)
        selected_id = selected_opt.split(" — ")[0]

        ctx = build_agent_context(db, selected_id, as_of_date=as_of_date)
        col_left, col_right = st.columns([1, 2])
        with col_left:
            st.markdown("#### Grounded Work Stats")
            st.json(ctx["work_stats"] if ctx["work_stats"] else {"note": f"Minimal operational stats visible as of {as_of_date}"})
            st.markdown("#### Visibility Scope")
            st.caption(ctx["visibility_scope"])
            st.markdown("#### Assumed Personal Profile (`ASSUMPTIONS.md`)")
            st.info(ctx["assumed_personal_context"])

        with col_right:
            iv_question = st.text_input(
                f"Ask {persona_map[selected_id]['full_name']} a question:",
                value="How are things actually going on your team right now?",
                key="iv_question",
            )
            if st.button("Interview Colleague", type="primary") and iv_question.strip():
                with st.spinner(f"Interviewing {persona_map[selected_id]['full_name']} as of {as_of_date}..."):
                    iv_res = interview_agent(db, selected_id, iv_question.strip(), as_of_date=as_of_date)
                st.success(f"**{iv_res['full_name']} ({iv_res['title']})** *(Model: `{iv_res['model_used']}`)*")
                st.write(iv_res["response"])
                with st.expander("🔎 Grounded Citations"):
                    for c in iv_res["citations"]:
                        st.markdown(f"- `{c}`")

    else:
        panel_preset = st.selectbox(
            "Select Department or Conflict Pair:",
            [
                "Engineering (Vikram, Priya, Arjun, Sneha, Rahul)",
                "Marketing vs Finance (Nikhil VX006, Meera VX003, Aisha VX011)",
                "Atlas Leadership Conflict (Vikram VX004, Priya VX007, Sneha VX012)",
                "Finance (Meera, Karthik, Fatima)",
                "People & Ops (Deepa, Rohan, Lakshmi)",
                "Marketing (Nikhil, Aisha, Siddharth)",
            ],
        )
        preset_target_map = {
            "Engineering (Vikram, Priya, Arjun, Sneha, Rahul)": "Engineering",
            "Marketing vs Finance (Nikhil VX006, Meera VX003, Aisha VX011)": "VX006,VX003,VX011",
            "Atlas Leadership Conflict (Vikram VX004, Priya VX007, Sneha VX012)": "VX004,VX007,VX012",
            "Finance (Meera, Karthik, Fatima)": "Finance",
            "People & Ops (Deepa, Rohan, Lakshmi)": "People & Ops",
            "Marketing (Nikhil, Aisha, Siddharth)": "Marketing",
        }
        panel_target = preset_target_map[panel_preset]
        panel_q = st.text_input(
            "Panel Question:",
            value="What is the real status and biggest risk right now?",
            key="panel_q",
        )
        if st.button("Run Panel Cross-Check", type="primary") and panel_q.strip():
            with st.spinner(f"Querying panel `{panel_target}` as of {as_of_date}..."):
                p_res = panel_interview(db, panel_target, panel_q.strip(), as_of_date=as_of_date)
            st.warning(p_res["truth_synthesis"])
            p_cols = st.columns(min(3, len(p_res["responses"])))
            for idx, r in enumerate(p_res["responses"]):
                with p_cols[idx % len(p_cols)]:
                    st.markdown(
                        f"""
                        <div class="metric-card" style="color: #111827;">
                            <strong style="color: #111827;">{r['full_name']}</strong> <code style="color: #111827; background-color: #e5e7eb; padding: 1px 5px; border-radius: 4px; font-size: 0.85em;">{r['emp_id']}</code><br/>
                            <span style="color: #4b5563; font-size: 0.85em;">{r['title']} — {r['department']}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.write(r["response"])
                    st.caption(f"Sources: {', '.join(r['citations'][:2])}")
