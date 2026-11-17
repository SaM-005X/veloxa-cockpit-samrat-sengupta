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

---

## Day 2 (`2026-11-17`)

### 1. Tasks Delegated to AI
- Inspected all 10 real files in `Day2_Tue_17Nov` (`Hiring_Tracker.xlsx`, `Leave_Register.xlsx`, `Pulse_Survey.xlsx`, `Resignation_Letter_SM.pdf`, emails `06.eml`, `07.eml`, `10.eml`, `11.eml`, `T3_Head_of_People_Call.docx`, `T6a_CEO_Voice_Note.docx`).
- Built Day 2 ingestion module ([`ingest/day2_loader.py`](ingest/day2_loader.py)) mapping requisitions to `hiring_reqs`, leave records to `leave_records`, quarterly pulse scores to `pulse_surveys`, PDFs to `documents`, emails to `emails`, seeded 18 aliases, 14 evidence items (`E022`..`E035`), and 3 cross-source conflicts (`C06`..`C08`).
- Developed the Ranked Risk Engine ([`cockpit/risk_engine.py`](cockpit/risk_engine.py)) implementing Point-in-Time temporal isolation (Day 1 vs Day 2) and default Top 3 ranking per Voice Note `T6a`.
- Authored the formal executive response to CEO Voice Note `T6a` ([`voice_notes/T6a_response.md`](voice_notes/T6a_response.md)) detailing the Top 3 implementation and the constructive pushback for retaining an expandable `#4+` audit drawer.
- Built the interactive Streamlit Executive Cockpit ([`app.py`](app.py)) with a Point-in-Time Time Machine selector, Top 3 default landing view, Voice Note player/response viewer, Evidence & Conflict explorer, and Stage 3 placeholders.
- Extended the CLI runner ([`run.py`](run.py)) with `--ingest-day2`, `--ingest-all`, and `--worries` flags.
- Authored comprehensive Stage 2 tests ([`tests/test_stage2_day2.py`](tests/test_stage2_day2.py)) testing real counts, Point-in-Time non-leakage, anonymity guardrails, and SQLite/PostgreSQL parity.

### 2. Mistakes, Gaps & Corrections
- **Rohan Banerjee's Inflated Claims in T3:** AI initially took Rohan's statements ("22 open roles in April", "lost 6 in August") as factual talent benchmarks. Direct cross-examination against `Hiring_Tracker.xlsx` (`Keka Hire`) revealed only 6 requisitions tracked in total (`REQ-011`, `REQ-013`–`REQ-017` with `REQ-012` missing), of which only 2 were paused in August (`REQ-014`/`REQ-015`), and only 1 resignation occurred in the company (`VX013` Siddharth Mehta). Coded `C06` to resolve the verbal claim in favor of official HRMS records.
- **Culture Amp Anonymity Enforcement:** Rather than attempting to display or extract individual comments from `Pulse_Survey.xlsx`, verified that every team at Veloxa has fewer than 6 members (`Engineering: 5`, `Finance: 3`, `People & Ops: 3`, `Marketing: 3`, `Sales: 2`, `Support: 2`), meaning qualitative comments are withheld by design. Enforced `comments_withheld = True` with reason `"Culture Amp anonymity threshold: team size < 6"` across all 24 pulse records.
- **Leave Register Abbreviated Mapping:** `Leave_Register.xlsx` used initials and abbreviated names (`A. Das`, `P. Nair`, `K. Subramanian`, `F. Sheikh`, `S. Kulkarni`, `N. Bose`, `A. Khan`, `R. Verma`, `S. Mehta`, `D. Joshi`, `L. Pillai`, `V. Menon`). Mapped each alias to its canonical `VX*` ID to maintain relational integrity with `employees`.
- **Dual-Database Parity:** Re-ran full sync and verified exact parity between local `veloxa.db` and Supabase PostgreSQL across all 15 operational and evidence tables (6 hiring reqs, 19 leave records, 24 pulse surveys, 35 evidence rows, 8 conflicts, 11 documents, 7 emails).
