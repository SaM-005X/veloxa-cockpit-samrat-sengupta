# Veloxa CXO Cockpit

An evidence-grounded, point-in-time executive intelligence cockpit for **Veloxa Technologies**, built for the Hiyaku Systems 5-Day Hackathon.

> **Current Status:** **Stage 4 (Day 4 — Thursday, 19 Nov 2026)**.  
> Day 1–4 data ingested (`veloxa.db` + Supabase PostgreSQL parity across all 21 tables), Policy Guardrails active (`T2` salary ban, `11.eml` `< 6` survey anonymity, `T6c` quit-risk ranking & Slack scraping refusal with `status="refused_guardrail"`, `"I don't know"` missing-system honesty), `T6d` Resignation & SPOF Impact Analyzer (`analyze_resignation_impact()`), Groq-powered CEO Q&A Engine (`qwen/qwen3.8-27b` primary + deterministic offline fallback), 14 Colleague AI Agents (1-on-1 + Department/Conflict Panel Cross-Check), and CEO Voice Notes `T6a`–`T6d` answered.

---

## Quick Start (One-Command Setup & Verification)

```bash
pip install -r requirements.txt && python run.py --setup --ingest-all --worries --test
```

### Launching the Executive Streamlit Web UI

```bash
streamlit run app.py
```
The cockpit opens directly to **Tab 1: "What Should I Worry About? (Top 3)"** per CEO Voice Note `T6a`, featuring:
- **Time Machine Selector (Sidebar):** Toggle operating horizon across `2026-11-19 (Day 4)`, `2026-11-18 (Day 3)`, `2026-11-17 (Day 2)`, and `2026-11-16 (Day 1)` with strict historical non-leakage.
- **Top 3 Strategic Worries & Day 4 `T6d` Board Crisis Spotlight:** Critical/High severity cards with confidence ratings, summaries, actionable next steps, verified citations (`#4+` items retained in expandable drawer), and Priya Nair (`VX007`) resignation SPOF impact metrics when `as_of_date >= 2026-11-19`.
- **Voice Note Responses (`T6a`–`T6d`):** Executive decision briefs, `T6c` privacy/non-surveillance refusal, and `T6d` Board reset recommendations.
- **Evidence & Conflict Explorer:** Filterable grid of atomic evidence (`E001`..`E057`), cross-source contradictions (`C01`..`C15`), Jira stories/versions, Git commits, PagerDuty incidents, On-Call Rota, Hiring, Leave, Pulse, and GL tables.
- **CEO Q&A Chatbot (Tab 4):** Interactive executive Q&A with sample prompt buttons, confidence badges, sources-disagree alerts, guardrail refusal banners, and expandable citations.
- **14 Colleague AI Agents (Tab 5):** Interactive **1-on-1 Interview** (grounded Point-in-Time work stats + assumed personal profile) and **Department / Conflict Panel Cross-Check** with Cockpit Truth Synthesis.

---

## CLI Runner Usage (`run.py`)

```bash
# Initialize SQLite & Supabase PostgreSQL schemas
python run.py --setup

# Ingest raw data drops (uses VELOXA_DATA_DIR from .env by default)
python run.py --ingest-day1
python run.py --ingest-day2
python run.py --ingest-day3
python run.py --ingest-day4
python run.py --ingest-all

# Display Top 3 Ranked Worries from the terminal (per T6a)
python run.py --worries --as-of 2026-11-19
python run.py --worries --as-of 2026-11-18
python run.py --worries --as-of 2026-11-17
python run.py --worries --as-of 2026-11-16

# Run Priya Nair (VX007) Resignation & SPOF Impact Analyzer (T6d)
python run.py --impact VX007 --as-of 2026-11-19

# Ask the grounded CEO Q&A Cockpit
python run.py --ask "What does Priya Nair's resignation do to Atlas v3?" --as-of 2026-11-19

# Interview one of the 14 colleague AI personas (1-on-1)
python run.py --interview VX007 "How is Atlas v3 workload going for you?" --as-of 2026-11-19

# Run a Multi-Agent Panel Cross-Check (department name or comma-separated VX IDs)
python run.py --panel "VX006,VX003" "What was our half-year Marketing spend?" --as-of 2026-11-19
python run.py --panel Engineering "What is the impact on Atlas v3 right now?" --as-of 2026-11-19

# Inspect database row counts and backend parity
python run.py --status

# Run full automated test suite
python run.py --test
```

---

## Environment Configuration (`.env`)

Copy `.env.example` to `.env` to configure external connections:
- `DATABASE_URL`: Supabase PostgreSQL connection string (if omitted, the cockpit automatically runs on the local `veloxa.db` SQLite mirror).
- `GROQ_API_KEY`: Groq Cloud API key for LLM synthesis (falls back seamlessly to the deterministic SQL + evidence-index synthesizer when unset or offline).
- `GROQ_MODEL`: Optional Groq model override (defaults to `qwen/qwen3.8-27b`, with automatic fallback to `llama-3.3-70b-versatile` and `openai/gpt-oss-120b` on API errors).
- `VELOXA_DATA_DIR`: Path to local `Veloxa_Hackathon_Release_Packs` folder for ingesting raw drops.

---

## Running Automated Tests

```bash
python -m pytest -v
```
Covers Stage 1, Stage 2, Stage 3, and Stage 4 tests:
1. Schema initialization, dual-DB parity across all 21 tables, and temporal release mapping.
2. Day 1–4 ingestion (`Employee_Master`, `GL_Export`, `Payroll_Register`, `Hiring_Tracker`, `Leave_Register`, `Pulse_Survey`, `Jira_Export_ATLAS`, `git_log.csv` [1,453 commits], `Incidents_Aug-Oct_2026`, `OnCall_Rota`, `Invoice_PIS-114`, `Atlas_Launch_Kit_v1`, `Email_Printouts`, 11 `.eml` emails, and `T1`–`T6d` transcripts/voice notes).
3. Strict Point-in-Time isolation (`2026-11-16`, `2026-11-17`, and `2026-11-18` leak zero future-day records).
4. Guardrails & honest uncertainty (`T2` salary refusal, `11.eml` `< 6` team survey comment refusal, `T6c` quit-risk ranking & Slack scraping refusal with `status="refused_guardrail"`, `"I don't know"` for missing Slack/HubSpot/LinkedIn/`REQ-012`).
5. Grounded CEO Q&A citations, conflict detection (`sources_disagree == True`), `T6d` resignation SPOF impact analysis (`VX007`), and 14 AI Agent persona consistency & panel cross-checks.

---

## Project Documentation & Governance Logs
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 5-layer design, relational schema, entity resolution, guardrails, Q&A, impact analysis, and 14-agent architecture.
- [`ASSUMPTIONS.md`](ASSUMPTIONS.md) — Logged assumptions (`A01`..`A33`, including all 14 AI persona profiles and Day 4 notice/privacy assumptions) with source citations, confidence ratings, and falsifiability criteria.
- [`TRANSCRIPT_NOTES.md`](TRANSCRIPT_NOTES.md) — Verified transcript mishearings and cross-source contradictions (`C01`..`C15`) across `T1`–`T6d`.
- [`DECISIONS.md`](DECISIONS.md) — Architectural and product trade-offs (`D01`..`D12`).
- [`voice_notes/T6a_response.md`](voice_notes/T6a_response.md), [`voice_notes/T6b_response.md`](voice_notes/T6b_response.md), [`voice_notes/T6c_response.md`](voice_notes/T6c_response.md), & [`voice_notes/T6d_response.md`](voice_notes/T6d_response.md) — Written responses to CEO Voice Notes `T6a`–`T6d`.
- [`AI_LOG.md`](AI_LOG.md) — Comprehensive audit log of AI-assisted tasks, mistakes caught, and human verification.
