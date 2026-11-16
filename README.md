# Veloxa CXO Cockpit

An evidence-grounded, point-in-time executive intelligence cockpit for **Veloxa Technologies**, built for the Hiyaku Systems 5-Day Hackathon.

> **Current Status:** Stage 1 (Day 1 — Mon 16 Nov 2026). Core database schema, SQLite/Supabase dual storage layer, temporal isolation rules, Day 1 ingestion pipeline, and foundational tests are in place.

---

## Quick Start (One-Command Setup & Verification)

```bash
pip install -r requirements.txt && python run.py --setup --test
```

### Optional Configuration (`.env`)
Copy `.env.example` to `.env` if you want to connect cloud services:
- `DATABASE_URL`: Supabase PostgreSQL connection string (if omitted, the cockpit automatically runs on the local `veloxa.db` SQLite mirror).
- `GROQ_API_KEY`: Groq Cloud API key for LLM synthesis (falls back to deterministic citation formatting when unset).
- `VELOXA_DATA_DIR`: Path to local `Veloxa_Hackathon_Release_Packs` folder for ingesting raw drops.

### Ingesting Day 1 Data
```bash
python run.py --setup --ingest-day1 /path/to/Veloxa_Hackathon_Release_Packs
```

---

## Running Automated Tests

```bash
python -m pytest -v
```

---

## Project Documentation
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 5-layer design, schema, entity resolution, and point-in-time model.
- [`ASSUMPTIONS.md`](ASSUMPTIONS.md) — Logged operational and persona assumptions with confidence and falsifiability criteria.
- [`TRANSCRIPT_NOTES.md`](TRANSCRIPT_NOTES.md) — Verified transcript mishearings and cross-source contradictions.
- [`DECISIONS.md`](DECISIONS.md) — Architectural and product trade-offs.
- [`AI_LOG.md`](AI_LOG.md) — Log of AI-assisted work, caveats, and manual verifications.
