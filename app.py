"""Veloxa CXO Cockpit — Executive Intelligence Dashboard.

Default Landing View: What Should I Worry About? (Top 3 Ranked Worries per T6a)
Includes Point-in-Time 'Time Machine' Isolation (Day 1 vs Day 2).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from cockpit.risk_engine import get_ranked_worries
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
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 12px;
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
    st.sidebar.write(f"☁️ **Cloud Primary:** `Supabase Postgres` (Synced)")
else:
    st.sidebar.write(f"☁️ **Cloud Primary:** `Offline / Local Mirror`")

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
    "🎙️ Voice Note Responses (T6a)",
    "🔍 Evidence & Conflict Explorer",
    "🤖 CEO Q&A Chatbot (Stage 3)",
    "👥 14 Colleague AI Agents (Stage 3)",
])

# ----------------------------------------------------------------------------
# TAB 1: What Should I Worry About? (Default Landing per T6a)
# ----------------------------------------------------------------------------
with tab1:
    st.subheader(f"Top Strategic Worries (As of {as_of_date})")
    st.info("💡 **Executive Briefing (Voice Note T6a Default):** Opens directly to the Top 3 verified risks by default. Lower-ranked compliance & financial control items remain available in the expandable drawer below.")

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

            # Evidentiary Citations Expander
            with st.expander(f"🔎 View Evidentiary Basis ({len(w['citations'])} verified sources)", expanded=False):
                for c in w["citations"]:
                    st.markdown(f"**[{c['evidence_id']}] `{c['source_file']}` — `{c['location']}`** *(Reliability: {c['reliability']})*")
                    st.write(f"> \"{c['fact_text']}\"")

    # Expandable Drawer for #4+
    remaining_worries = all_worries[3:]
    if remaining_worries:
        st.markdown("---")
        with st.expander(f"📂 Expand Remaining Risks (#{len(top_worries)+1}–#{len(all_worries)}) — Financial & Governance Audit Trail", expanded=False):
            st.caption("These items do not represent existential day-to-day fires but must remain tracked for investor due diligence and financial control compliance.")
            for rw in remaining_worries:
                st.markdown(f"#### #{rw['rank']} [{rw['severity']}] {rw['title']}")
                st.write(f"**Summary:** {rw['summary']}")
                st.write(f"**Recommended Action:** {rw['recommended_action']}")
                with st.expander(f"Citations for #{rw['rank']}", expanded=False):
                    for c in rw["citations"]:
                        st.markdown(f"- **[{c['evidence_id']}]** `{c['source_file']}` (`{c['location']}`): {c['fact_text']}")
                st.markdown("---")

# ----------------------------------------------------------------------------
# TAB 2: Voice Note Responses (T6a)
# ----------------------------------------------------------------------------
with tab2:
    st.subheader("🎙️ CEO Voice Note Responses")

    # T6a Card
    st.markdown("### Voice Note `T6a`: Morning Brief & Risk View")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("""
        **Speaker:** Ananya Rao (CEO)  
        **Release Date:** 2026-11-17  
        **Status:** <span class="badge-resolved">Implemented with Guardrail</span>  
        **Decision Document:** `voice_notes/T6a_response.md`
        """, unsafe_allow_html=True)
        st.audio(b"", format="audio/wav")  # Placeholder visual
        st.info('🗣️ **Transcript:** *"Hi, quick one. I won\'t type questions every morning, na. When I open it, it should just tell me what to worry about. Top three. Okay, bye."*')

    with col2:
        t6a_file = Path("voice_notes/T6a_response.md")
        if t6a_file.is_file():
            st.markdown(t6a_file.read_text(encoding="utf-8"))
        else:
            st.warning("voice_notes/T6a_response.md not found.")

# ----------------------------------------------------------------------------
# TAB 3: Evidence & Conflict Explorer
# ----------------------------------------------------------------------------
with tab3:
    st.subheader(f"🔍 Grounded Evidence & Cross-Source Conflicts (As of {as_of_date})")

    explorer_view = st.radio(
        "Select Dataset:",
        ["Evidence Index", "Active Conflicts", "Hiring Requisitions", "Leave Register", "Pulse Surveys", "GL Transactions"],
        horizontal=True,
    )

    if explorer_view == "Evidence Index":
        rows = db.query(
            """SELECT evidence_id, source_file, location, fact_text, reliability, event_date, conflict_group_id
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

    elif explorer_view == "Hiring Requisitions":
        if as_of_date >= "2026-11-17":
            h_rows = db.query("SELECT * FROM hiring_reqs WHERE release_date <= ? ORDER BY req_id", (as_of_date,))
            st.dataframe(pd.DataFrame(h_rows), use_container_width=True)
        else:
            st.warning("Hiring Requisitions are part of Day 2 (2026-11-17) and are not visible under Day 1 operating horizon.")

    elif explorer_view == "Leave Register":
        if as_of_date >= "2026-11-17":
            l_rows = db.query("SELECT * FROM leave_records WHERE release_date <= ? ORDER BY start_date", (as_of_date,))
            st.dataframe(pd.DataFrame(l_rows), use_container_width=True)
        else:
            st.warning("Leave Register is part of Day 2 (2026-11-17) and is not visible under Day 1 operating horizon.")

    elif explorer_view == "Pulse Surveys":
        if as_of_date >= "2026-11-17":
            p_rows = db.query("SELECT survey_period, department, respondent_count, avg_score, comments_withheld, withhold_reason FROM pulse_surveys WHERE release_date <= ? ORDER BY survey_period, department", (as_of_date,))
            st.dataframe(pd.DataFrame(p_rows), use_container_width=True)
        else:
            st.warning("Pulse Survey results are part of Day 2 (2026-11-17) and are not visible under Day 1 operating horizon.")

    elif explorer_view == "GL Transactions":
        gl_rows = db.query("SELECT voucher_id, txn_date, account_name, cost_center, vendor_name, amount_inr, description, entered_by FROM gl_transactions WHERE release_date <= ? ORDER BY txn_date", (as_of_date,))
        st.dataframe(pd.DataFrame(gl_rows), use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 4: CEO Q&A Chatbot (Stage 3 Preview)
# ----------------------------------------------------------------------------
with tab4:
    st.subheader("🤖 Grounded CEO Q&A Engine (Unlocking Stage 3 — Wed 18 Nov)")
    st.markdown("""
    The conversational cockpit engine pairs **Groq Cloud API (`llama-3.3-70b-versatile`)** with strict **SQL metric computation and evidence graph retrieval**.

    ### 🛡️ Non-Negotiable Guardrails Configured:
    1. **Strict Individual Salary Redaction (`T2_CFO_Call`):** Refuses disclosure of individual employee compensation; provides team/aggregate figures only.
    2. **Pulse Survey Anonymity Protection (`Pulse_Survey.xlsx`, `11.eml`):** Refuses comment-level disclosure for teams smaller than 6 respondents.
    3. **Prohibition on Private Surveillance / Flight-Risk Scoring:** Refuses requests to scrape private Slack messages or rank individuals by likelihood to quit.
    4. **Missing Data Transparency ("I don't know"):** Explicitly states when requested metrics (e.g. HubSpot pipeline, LinkedIn campaign spend breakdown) are not in the Veloxa data room.
    """)
    st.text_input("Ask a strategic question (e.g., 'What is our actual runway and Atlas delivery risk?'):", disabled=True, placeholder="Available in Stage 3...")

# ----------------------------------------------------------------------------
# TAB 5: 14 Colleague AI Agents (Stage 3 Preview)
# ----------------------------------------------------------------------------
with tab5:
    st.subheader("👥 The 14 Colleague Personas (Roster Active)")
    st.caption("14 synthetic colleagues across Engineering, Finance, People & Ops, and Marketing. 1-on-1 interviews and department cross-examination unlock in Stage 3.")

    colleagues = db.query(
        """SELECT entity_id, full_name, department, title, manager_id, location, join_date
           FROM employees
           WHERE is_agent_persona = 1
           ORDER BY department, entity_id"""
    )
    if colleagues:
        cols = st.columns(3)
        for idx, c in enumerate(colleagues):
            with cols[idx % 3]:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <strong>{c['full_name']}</strong> (`{c['entity_id']}`)<br/>
                        <span style="color: #4b5563; font-size: 0.9em;">{c['title']} — {c['department']}</span><br/>
                        <span style="font-size: 0.8em; color: #6b7280;">📍 {c['location']} | Joined {c['join_date']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
