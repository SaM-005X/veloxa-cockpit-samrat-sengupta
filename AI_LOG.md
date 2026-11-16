# AI Collaboration Log

> Honest record of tasks delegated to AI, where AI made mistakes or hit environment boundaries, and what was manually verified or corrected.

---

## Day 1 (`2026-11-16`)

### 1. Tasks Delegated to AI
- Scaffolded repository structure (`.gitignore`, `.env.example`, `requirements.txt`, `run.py`).
- Designed unified relational DDL ([`db/schema.sql`](db/schema.sql)) and dual SQLite/PostgreSQL manager ([`db/database.py`](db/database.py)).
- Implemented temporal tagging rules ([`ingest/temporal.py`](ingest/temporal.py)), Day 1 parser ([`ingest/day1_loader.py`](ingest/day1_loader.py)), and Stage 1 foundation tests ([`tests/test_stage1_foundation.py`](tests/test_stage1_foundation.py)).
- Drafted initial Day 1 documentation (`ARCHITECTURE.md`, `README.md`, `ASSUMPTIONS.md`, `TRANSCRIPT_NOTES.md`, `DECISIONS.md`).

### 2. Mistakes, Gaps & Corrections
- **Environment Boundary Caught:** The remote workspace VM did not have the Supabase MCP connector or the local Windows `Day1_Mon_16Nov` files mounted directly. AI correctly flagged both blockers instead of fabricating database rows or guessing unverified spreadsheet column layouts.
- **Column-Mapping Caution:** Because raw Day 1 `.xlsx` headers have not yet been inspected directly inside the VM, `ingest/day1_loader.py` uses flexible candidate column aliases (`_pick(...)`), logged as pending verification (`A05` in `ASSUMPTIONS.md`) and tested against synthetic Day 1 fixtures until the raw pack is uploaded.
- **Temporal Scope Discipline:** Ensured Day 1 documentation and `TRANSCRIPT_NOTES.md` strictly reflect `Day1_Mon_16Nov` knowledge only, avoiding any Day 2–4 spoilers.
