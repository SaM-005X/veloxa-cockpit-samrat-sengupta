# Veloxa CXO Cockpit

An evidence-grounded, point-in-time executive intelligence cockpit for **Veloxa Technologies**, built for the Hiyaku Systems 5-Day Hackathon.

> **Current Status:** **Stage 2 (Day 2 — Tuesday, 17 Nov 2026)**.  
> Day 1 and Day 2 data ingested, Point-in-Time isolation enforced, Ranked Risk Engine operational, CEO Voice Note `T6a` answered with zero-prompt Top 3 default landing, and interactive Streamlit web dashboard active. 14 automated tests passing with 100% SQLite/Supabase parity.

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
- **Time Machine Selector (Sidebar):** Toggle operating horizon between `2026-11-16 (Day 1)` and `2026-11-17 (Day 2)` with strict historical non-leakage.
- **Top 3 Strategic Worries:** Critical/High severity cards with confidence ratings, summaries, actionable next steps, and verified evidence citations.
- **Audit & Governance Drawer:** Expandable `#4+` drawer retaining lower-ranked compliance and financial control findings.
- **Voice Note Responses (`T6a`):** Executive decision brief and constructive pushback rationale.
- **Evidence & Conflict Explorer:** Filterable grid of atomic evidence (`E001`..`E035`), cross-source contradictions (`C01`..`C08`), and operational tables.
- **Stage 3 Previews:** Previews of Grounded CEO Q&A Engine and 14 Colleague AI Agent personas.

---

## CLI Runner Usage (`run.py`)

The unified CLI runner provides deterministic entry points for setup, ingestion, risk analysis, and testing:

```bash
# Initialize SQLite & Supabase PostgreSQL schemas
python run.py --setup

# Ingest raw data drops (uses VELOXA_DATA_DIR from .env by default)
python run.py --ingest-day1
python run.py --ingest-day2
python run.py --ingest-all

# Display Top 3 Ranked Worries from the terminal (per T6a)
python run.py --worries --as-of 2026-11-17

# Verify Point-in-Time isolation (ranks worries strictly using Day 1 evidence)
python run.py --worries --as-of 2026-11-16

# Inspect database row counts and backend parity
python run.py --status

# Run full automated test suite
python run.py --test
```

---

## Environment Configuration (`.env`)

Copy `.env.example` to `.env` to configure external connections:
- `DATABASE_URL`: Supabase PostgreSQL connection string (if omitted, the cockpit automatically runs on the local `veloxa.db` SQLite mirror).
- `GROQ_API_KEY`: Groq Cloud API key for LLM synthesis (falls back to deterministic citation formatting when unset).
- `VELOXA_DATA_DIR`: Path to local `Veloxa_Hackathon_Release_Packs` folder for ingesting raw drops.

---

## Running Automated Tests

```bash
python -m pytest -v
```
Currently passes **14 automated tests** covering:
1. Schema initialization and table DDL.
2. Temporal release mapping and Point-in-Time non-leakage.
3. Day 1 ingestion (Employee master, Zoho GL, Jan–Mar payroll proration).
4. Day 2 ingestion (`Hiring_Tracker.xlsx`, `Leave_Register.xlsx`, `Pulse_Survey.xlsx`, `Resignation_Letter_SM.pdf`, emails `06`, `07`, `10`, `11`, transcripts `T3` and `T6a`).
5. Culture Amp survey anonymity (< 6 respondents enforces comments withheld).
6. Ranked Risk Engine output (`top_n=3` default vs. `top_n=None` full audit).
7. Supabase PostgreSQL and local SQLite mirror parity.

---

## Project Documentation & Governance Logs
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 5-layer design, relational schema, entity resolution, and temporal isolation model.
- [`ASSUMPTIONS.md`](ASSUMPTIONS.md) — Logged assumptions (`A01`..`A11`) with source citations, confidence ratings, and falsifiability criteria.
- [`TRANSCRIPT_NOTES.md`](TRANSCRIPT_NOTES.md) — Verified transcript mishearings and cross-source contradictions (`C01`..`C08`).
- [`DECISIONS.md`](DECISIONS.md) — Architectural and product trade-offs (`D01`..`D05`).
- [`voice_notes/T6a_response.md`](voice_notes/T6a_response.md) — Written response to CEO Voice Note `T6a`.
- [`AI_LOG.md`](AI_LOG.md) — Comprehensive audit log of AI-assisted tasks, human verification, and error corrections.
