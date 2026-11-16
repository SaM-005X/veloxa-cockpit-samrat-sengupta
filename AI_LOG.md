# AI Collaboration Log

> Honest record of tasks delegated to AI, where AI made mistakes or hit environment boundaries, and what was manually verified or corrected.

---

## Day 1 (`2026-11-16`)

### 1. Tasks Delegated to AI
- Scaffolded repository structure (`.gitignore`, `.env.example`, `requirements.txt`, `run.py`).
- Designed unified relational DDL ([`db/schema.sql`](db/schema.sql)) and dual SQLite/PostgreSQL manager ([`db/database.py`](db/database.py)).
- Implemented temporal tagging rules ([`ingest/temporal.py`](ingest/temporal.py)), Day 1 parser ([`ingest/day1_loader.py`](ingest/day1_loader.py)), and Stage 1 tests ([`tests/test_stage1_foundation.py`](tests/test_stage1_foundation.py)).
- Inspected all 15 real Day 1 files in `Day1_Mon_16Nov` (without touching Day 2–4 folders), configured Supabase project `kfjbhpiocjdbutaiuqgx`, ran schema migration + Day 1 ingestion into both local `veloxa.db` and Supabase PostgreSQL, and updated Day 1 documentation (`ARCHITECTURE.md`, `README.md`, `ASSUMPTIONS.md`, `TRANSCRIPT_NOTES.md`, `DECISIONS.md`).

### 2. Mistakes, Gaps & Corrections
- **Header-Row Mismatch Caught During Real-File Inspection:** The initial scaffold of `ingest/day1_loader.py` assumed row 1 was the header row (`pd.read_excel(..., header=0)`). Direct inspection of all 5 Day 1 `.xlsx` files revealed a **2-row preamble** (Row 1 = description banner, Row 2 = blank, **Row 3 = actual column headers**). Fixed via `_read_xlsx_sheet(...)` header-marker auto-detection while preserving Row 1 compatibility for unit-test fixtures.
- **Exact Column & Sheet Name Fixes:** Real-file inspection caught five column mismatches in the initial loader:
  1. `GL_Export_Apr-Sep_2026.xlsx` (`GL Apr-Sep`) uses `Voucher`, `Vendor / Payee`, `Ref`, `Cost Centre` (British spelling), `Amount (Rs.)`, `Narration`, `Entered By`.
  2. `Payroll_Register_Jan-Mar_2026.xlsx` (`Payroll Q4`) uses `Emp ID`, `Month` (`Jan-2026`..`Mar-2026`), `Days Payable`, `Gross (Rs.)`, `Net (Rs.)`, `Processed By`, and **omits `Department`**—which originally caused every department bucket to default to `"All"`. Fixed by parsing `Employee_Master.xlsx` first and joining `department` and `join_date` via `Emp ID`.
  3. `01.eml`–`03.eml` use RFC 2822 `Date` headers (`Sat, 28 Feb 2026 20:15:00 +0530`), where `sent_at[:10]` produced `"Sat, 28 Fe"` instead of ISO `YYYY-MM-DD`. Fixed via `email.utils.parsedate_to_datetime`.
  4. `Entity_Resolution.xlsx` and `Evidence_Index.xlsx` in Day 1 are blank candidate worksheets; added curated Day 1 `entity_aliases` (22), `evidence_index` (21), and `conflicts` (5) seeding strictly scoped to `2026-11-16`.
  5. Added PostgreSQL `ON CONFLICT` upsert sync in `ingest/day1_loader.py` and verified row-count parity between local `veloxa.db` and Supabase PostgreSQL (`kfjbhpiocjdbutaiuqgx`).
- **Temporal Scope Discipline:** Verified Day 1 ingestion, tests, and documentation strictly read `Day1_Mon_16Nov` (`2026-11-16`) only, with zero Day 2–4 leakage.
