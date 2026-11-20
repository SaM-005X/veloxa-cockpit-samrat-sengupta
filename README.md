# Veloxa CXO Cockpit

An evidence-grounded, point-in-time executive intelligence cockpit for **Veloxa Technologies**, built for the Hiyaku Systems 5-Day Hackathon.

> **Current Status:** **Stage 5 — Final Submission & Code Freeze (Friday, 20 Nov 2026)**.  
> 100% self-contained for fresh-clone offline evaluation via a path-sanitized portable seed ([`data/seed/veloxa_seed.json`](data/seed/veloxa_seed.json)) with automatic **Supabase PostgreSQL + RLS** parity when `DATABASE_URL` is configured. Features strict 4-day Point-in-Time isolation (`2026-11-16`..`2026-11-19`), Policy Guardrails (`T2` salary ban, `11.eml` `< 6` survey anonymity, `T6c` quit-risk ranking & Slack scraping refusal with `status="refused_guardrail"`, `"I don't know"` missing-system honesty), `T6d` Resignation & SPOF Impact Analyzer (`analyze_resignation_impact()`), Groq-powered CEO Q&A Engine (`qwen/qwen3.8-27b` primary + deterministic offline fallback), 14 Colleague AI Agents (1-on-1 + Department/Conflict Panel Cross-Check), CEO Voice Notes `T6a`–`T6d`, and a **38-test automated verification suite**.

---

## Quick Start (One-Command Setup & Verification — Works Offline on Fresh Clone)

```bash
pip install -r requirements.txt && python run.py --setup --ingest-all --worries --status --test
```

How fresh-clone hydration works automatically:
- If `VELOXA_DATA_DIR` points to mounted `Veloxa_Hackathon_Release_Packs`, `--ingest-all` parses all raw Day 1–4 files (`.xlsx`, `.csv`, `.pdf`, `.eml`, `.docx`) and syncs both `veloxa.db` and Supabase PostgreSQL.
- If `VELOXA_DATA_DIR`, `DATABASE_URL`, and `GROQ_API_KEY` are **unset** (e.g., an evaluator running from a clean fresh clone without `.env` or raw archives), `--ingest-all` automatically hydrates a clean `veloxa.db` SQLite database from the tracked portable seed snapshot ([`data/seed/veloxa_seed.json`](data/seed/veloxa_seed.json)), renders the deterministic Top 3 worries, and executes the automated test suite cleanly.

### Launching the Executive Streamlit Web UI

```bash
streamlit run app.py
```
*(Or run `python run.py --setup --ingest-all --ui` in a single command.)*

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

# Ingest raw data drops (uses VELOXA_DATA_DIR if mounted, or falls back to portable seed for --ingest-all)
python run.py --ingest-day1
python run.py --ingest-day2
python run.py --ingest-day3
python run.py --ingest-day4
python run.py --ingest-all

# Explicitly hydrate SQLite from portable seed or export a sanitized seed snapshot
python run.py --seed
python run.py --export-seed

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

# Launch Streamlit Executive UI
python run.py --ui
```

---

## Environment Configuration (`.env`, Optional)

All core features, offline seed hydration, deterministic SQL Q&A, 14-agent interviews, guardrails, and tests run **with zero `.env` configuration**. To enable optional cloud PostgreSQL sync or live Groq LLM prose synthesis, copy `.env.example` to `.env`:
- `DATABASE_URL`: Supabase PostgreSQL connection string (when omitted, the cockpit runs seamlessly on the local `veloxa.db` SQLite mirror).
- `GROQ_API_KEY`: Groq Cloud API key for LLM synthesis (falls back seamlessly to the deterministic SQL + evidence-index synthesizer when unset or offline).
- `GROQ_MODEL`: Optional Groq model override (defaults to `qwen/qwen3.8-27b`, with automatic fallback to `llama-3.3-70b-versatile` and `openai/gpt-oss-120b` on API errors).
- `VELOXA_DATA_DIR`: Path to local `Veloxa_Hackathon_Release_Packs` folder for ingesting raw drops.

---

## Running Automated Tests (38 Tests Total)

```bash
python -m pytest -v
```
Covers Stage 1, Stage 2, Stage 3, Stage 4, and Stage 5 tests across:
1. Schema initialization, dual-DB parity across all 21 tables, and temporal release mapping.
2. Day 1–4 ingestion (`Employee_Master`, `GL_Export`, `Payroll_Register`, `Hiring_Tracker`, `Leave_Register`, `Pulse_Survey`, `Jira_Export_ATLAS`, `git_log.csv` [1,453 commits], `Incidents_Aug-Oct_2026`, `OnCall_Rota`, `Invoice_PIS-114`, `Atlas_Launch_Kit_v1`, `Email_Printouts`, 11 `.eml` emails, and `T1`–`T6d` transcripts/voice notes) + portable offline seed hydration (`data/seed/veloxa_seed.json`).
3. Strict Point-in-Time isolation across all 4 dates (`2026-11-16`, `2026-11-17`, `2026-11-18`, `2026-11-19`) with zero future leakage.
4. **12 explicit refusal, missing-data uncertainty & PIT tests** (`T2` salary refusal across full/first-name variants, `11.eml` `< 6` team survey comment refusal, `T6c` quit-risk ranking & Slack scraping refusal with `status="refused_guardrail"`, `"I don't know"` for missing Slack/HubSpot/LinkedIn/`REQ-012`/Linear/Confluence/post-Sep GL & payroll).
5. Grounded CEO Q&A citations, conflict detection (`sources_disagree == True`), `T6d` resignation SPOF impact analysis (`VX007`), `T6b` temporal `reporting_lines` resilience, and all 14 AI Agent personas (`is_agent_persona == 1`) & panel cross-checks.

---

## Repository File Map

| Path | Purpose |
| :--- | :--- |
| [`run.py`](run.py) | Single-command CLI runner (`--setup`, `--ingest-all`, `--seed`, `--export-seed`, `--worries`, `--impact`, `--ask`, `--interview`, `--panel`, `--status`, `--test`, `--ui`) |
| [`app.py`](app.py) | Streamlit CXO Cockpit 5-tab Executive UI with 4-day Time Machine & auto-hydration |
| [`db/schema.sql`](db/schema.sql) | Unified PostgreSQL + SQLite DDL across all 21 tables |
| [`db/database.py`](db/database.py) | Dual SQLite/Supabase PostgreSQL manager & temporal `get_reporting_line_as_of()` |
| [`db/seed.py`](db/seed.py) | Path-sanitized portable seed exporter & offline hydrator |
| [`data/seed/veloxa_seed.json`](data/seed/veloxa_seed.json) | Tracked Day 1–4 normalized database seed snapshot for offline fresh clones |
| [`ingest/`](ingest/) | `temporal.py` & Day 1–4 raw data pack loaders (`day1_loader.py`..`day4_loader.py`) |
| [`cockpit/`](cockpit/) | `guardrails.py`, `qa_engine.py`, & `risk_engine.py` (Top 3 worries & `T6d` SPOF impact analyzer) |
| [`agents/persona.py`](agents/persona.py) | 14 colleague AI personas (1-on-1 & Department/Conflict Panel Cross-Check) |
| [`voice_notes/`](voice_notes/) | Written responses & pushbacks to CEO Voice Notes `T6a`–`T6d` |
| [`tests/`](tests/) | `conftest.py` + `test_stage1_foundation.py`..`test_stage5_submission.py` (38 automated tests) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 5-layer system design, dual storage, entity resolution, guardrails, Q&A & agent specs |
| [`ASSUMPTIONS.md`](ASSUMPTIONS.md) | Logged assumptions (`A01`–`A34`, including all 14 persona profiles & Stage 5 packaging) |
| [`TRANSCRIPT_NOTES.md`](TRANSCRIPT_NOTES.md) | Verified ASR mishearings and cross-source contradictions (`C01`–`C15`) across `T1`–`T6d` |
| [`DECISIONS.md`](DECISIONS.md) | Architectural and product trade-offs (`D01`–`D13`) |
| [`AI_LOG.md`](AI_LOG.md) | Stage 1–5 audit log of AI-assisted tasks, mistakes caught, and human verification |
