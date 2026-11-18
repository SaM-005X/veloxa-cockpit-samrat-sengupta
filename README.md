# Veloxa CXO Cockpit

An evidence-grounded, point-in-time executive intelligence cockpit for **Veloxa Technologies**, built for the Hiyaku Systems 5-Day Hackathon.

> **Current Status:** **Stage 3 (Day 3 — Wednesday, 18 Nov 2026)**.  
> Day 1–3 data ingested (`veloxa.db` + Supabase PostgreSQL parity across all 21 tables), Policy Guardrails active (`T2` salary ban, `11.eml` `< 6` survey anonymity, `"I don't know"` missing-system honesty), Groq-powered CEO Q&A Engine (`qwen/qwen3-32b` + deterministic offline fallback), 14 Colleague AI Agents (1-on-1 + Department/Conflict Panel Cross-Check), and CEO Voice Notes `T6a` & `T6b` answered.

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
- **Time Machine Selector (Sidebar):** Toggle operating horizon across `2026-11-16 (Day 1)`, `2026-11-17 (Day 2)`, and `2026-11-18 (Day 3)` with strict historical non-leakage.
- **Top 3 Strategic Worries:** Critical/High severity cards with confidence ratings, summaries, actionable next steps, and verified evidence citations (`#4+` items retained in expandable drawer).
- **Voice Note Responses (`T6a` & `T6b`):** Executive decision briefs and constructive pushback rationale.
- **Evidence & Conflict Explorer:** Filterable grid of atomic evidence (`E001`..`E054`), cross-source contradictions (`C01`..`C13`), Jira stories/versions, Git commits, PagerDuty incidents, On-Call Rota, Hiring, Leave, Pulse, and GL tables.
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
python run.py --ingest-all

# Display Top 3 Ranked Worries from the terminal (per T6a)
python run.py --worries --as-of 2026-11-18
python run.py --worries --as-of 2026-11-17
python run.py --worries --as-of 2026-11-16

# Ask the grounded CEO Q&A Cockpit
python run.py --ask "When is Atlas v3 actually shipping and why do sources disagree?" --as-of 2026-11-18

# Interview one of the 14 colleague AI personas (1-on-1)
python run.py --interview VX007 "How is Atlas v3 workload going for you?" --as-of 2026-11-18

# Run a Multi-Agent Panel Cross-Check (department name or comma-separated VX IDs)
python run.py --panel "VX006,VX003" "What was our half-year Marketing spend?" --as-of 2026-11-18
python run.py --panel Engineering "Is Atlas v3 on track for September?" --as-of 2026-11-18

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
- `GROQ_MODEL`: Optional Groq model override (defaults to `qwen/qwen3-32b`, with automatic fallback to `llama-3.3-70b-versatile` and available Groq models on API errors).
- `VELOXA_DATA_DIR`: Path to local `Veloxa_Hackathon_Release_Packs` folder for ingesting raw drops.

---

## Running Automated Tests

```bash
python -m pytest -v
```
Covers Stage 1, Stage 2, and Stage 3 tests:
1. Schema initialization, dual-DB parity across all 21 tables, and temporal release mapping.
2. Day 1–3 ingestion (`Employee_Master`, `GL_Export`, `Payroll_Register`, `Hiring_Tracker`, `Leave_Register`, `Pulse_Survey`, `Jira_Export_ATLAS`, `git_log.csv` [1,453 commits], `Incidents_Aug-Oct_2026`, `OnCall_Rota`, `Invoice_PIS-114`, `Atlas_Launch_Kit_v1`, `Email_Printouts`, 11 `.eml` emails, and `T1`–`T6b` transcripts).
3. Strict Point-in-Time isolation (`2026-11-16` and `2026-11-17` leak zero Day 3 records).
4. Guardrails & honest uncertainty (`T2` salary refusal, `11.eml` `< 6` team survey comment refusal, `"I don't know"` for missing Slack/HubSpot/LinkedIn/`REQ-012`).
5. Grounded CEO Q&A citations, conflict detection (`sources_disagree == True`), and 14 AI Agent persona consistency & panel cross-checks.

---

## Project Documentation & Governance Logs
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 5-layer design, relational schema, entity resolution, guardrails, Q&A, and 14-agent architecture.
- [`ASSUMPTIONS.md`](ASSUMPTIONS.md) — Logged assumptions (`A01`..`A30`, including all 14 AI persona profiles) with source citations, confidence ratings, and falsifiability criteria.
- [`TRANSCRIPT_NOTES.md`](TRANSCRIPT_NOTES.md) — Verified transcript mishearings and cross-source contradictions (`C01`..`C13`) across `T1`–`T6b`.
- [`DECISIONS.md`](DECISIONS.md) — Architectural and product trade-offs (`D01`..`D09`).
- [`voice_notes/T6a_response.md`](voice_notes/T6a_response.md) & [`voice_notes/T6b_response.md`](voice_notes/T6b_response.md) — Written responses to CEO Voice Notes `T6a` and `T6b`.
- [`AI_LOG.md`](AI_LOG.md) — Comprehensive audit log of AI-assisted tasks, mistakes caught, and human verification.
