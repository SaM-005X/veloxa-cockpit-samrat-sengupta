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

---

## Day 3 (`2026-11-18`)

### 1. Tasks Delegated to AI
- Inspected all 14 real files in `Day3_Wed_18Nov` (`Jira_Export_ATLAS.xlsx`, `git_log.csv`, `Incidents_Aug-Oct_2026.xlsx`, `OnCall_Rota.xlsx`, `Atlas_Launch_Kit_v1.pdf`, `Invoice_PIS-114.pdf`, `Email_Printouts.pdf`, emails `04.eml`, `05.eml`, `08.eml`, `09.eml`, `T4_Head_of_Marketing_Call.docx`, `T5_VP_Engineering_Call.docx`, `T6b_CEO_Voice_Note.docx`), strictly excluding `Day4_Thu_19Nov`.
- Built [`ingest/day3_loader.py`](ingest/day3_loader.py) loading 1 Jira version (`Atlas GA`), 62 Jira stories, 1,453 git commits (converted to IST), 11 PagerDuty incidents, 17 on-call weeks, 6 documents, 4 emails, 21 aliases (`61` total), 19 evidence items `E036`–`E054` (`54` total), 5 conflicts `C09`–`C13` (`13` total), 14 `agent_profiles`, and `T6b` in `voice_note_decisions`.
- Updated [`db/database.py`](db/database.py) `table_counts()` to report all 21 tables and added `get_reporting_line_as_of()` for temporal org resilience (`T6b`), plus updated [`cockpit/risk_engine.py`](cockpit/risk_engine.py) for `as_of_date >= '2026-11-18'`.
- Built [`cockpit/guardrails.py`](cockpit/guardrails.py), [`cockpit/qa_engine.py`](cockpit/qa_engine.py), and [`agents/persona.py`](agents/persona.py) (14 colleague AI agents with 1-on-1 interview and Panel Cross-Check modes).
- Authored [`voice_notes/T6b_response.md`](voice_notes/T6b_response.md), updated interactive tabs in [`app.py`](app.py) and CLI commands in [`run.py`](run.py), added [`tests/test_stage3_day3.py`](tests/test_stage3_day3.py), and updated all 6 mandatory Markdown files.

### 2. Mistakes, Gaps & Corrections (Human Verification & Live Fixes)
- **Priya Nair Jira Count Precision (35 vs. 36):** Planning notes initially estimated Priya (`PN`, `VX007`) had `36/62` Jira stories. Direct inspection of `Jira_Export_ATLAS.xlsx` (`Issues` tab) showed **35/62 stories** (`131/233` story points: `21 Done`, `7 In Progress`, `7 To Do`), including `12/12` (`100%`) of `ATLAS-2`. Corrected every citation and risk summary to `35/62`.
- **Groq Model Availability & Fallback Discovery:** Testing `qwen/qwen3-32b` and `llama-3.3-70b-versatile` against the active Groq workspace returned `404 model_not_found`, whereas `qwen/qwen3.8-27b` and `openai/gpt-oss-120b` succeeded. Implemented an ordered fallback chain (`GROQ_MODEL`/`qwen/qwen3-32b` -> `llama-3.3-70b-versatile` -> `qwen/qwen3.8-27b` -> `openai/gpt-oss-120b` -> deterministic SQL + evidence-index synthesizer) plus regex `<think>...</think>` stripping.
- **Sneha (`VX012`) vs. Snehal (`EXT001`) Disambiguation:** Caught Vikram's conflation in `T5` (`"pulled Snehal off"`, `"postmortems ... owner: Snehal"`). Verified via `Incidents_Aug-Oct_2026.xlsx`, `OnCall_Rota.xlsx`, `08.eml`, and `Invoice_PIS-114.pdf` that Sneha Kulkarni (`VX012`) is the FTE SRE who handled all 3 August SEV1s, while Snehal / S. Patil (`EXT001`) is the external contractor starting `2026-08-18`.
- **Email_Printouts.pdf Cross-Verification:** Diffed `Email_Printouts.pdf` against all 11 individual `.eml` files (`01`–`11`) and verified 100% textual parity (only formatted in IST).
- **LLM Output Precision Refinements Caught During Live CLI Runs:**
  1. In initial live testing of `interview_agent("VX007")`, Priya described her 35 total stories as `"35 open stories"` because the context line lacked an explicit open vs. done split. Updated `build_agent_context` to report `"35 stories total (131 pts; 21 Done, 7 open In Progress + 7 To Do = 14 open)"`.
  2. In `panel_interview("VX006,VX003", "What was our half-year Marketing spend?")`, `matched_conflicts` initially returned conflicts in ID order (`C05, C07, C08`) ahead of `C12` ("Marketing Half-Year Spend"). Added relevance scoring by question keyword overlap + multi-panelist hits so `C12` ranks #1 in `truth_synthesis`.
- **Supabase Bulk Sync Performance:** Used `psycopg2.extras.execute_values` for the 1,453 `git_commits` rows and verified 100% identical row counts across all 21 tables between local `veloxa.db` and Supabase PostgreSQL.

---

## Day 4 (`2026-11-19`)

### 1. Tasks Delegated to AI
- Inspected `Day4_Thu_19Nov/transcripts/T6c_CEO_Voice_Note.docx` and `T6d_CEO_Voice_Note.docx`, and verified `Day4_Thu_19Nov` contains no `data_room` files.
- Built [`ingest/day4_loader.py`](ingest/day4_loader.py) (`ingest_day4`), updated [`ingest/temporal.py`](ingest/temporal.py) (`DAY4_FILES`), and wired `--ingest-day4`, `--impact`, and 4-day `--ingest-all` into [`run.py`](run.py).
- Loaded `VOICE_NOTE_T6C` & `VOICE_NOTE_T6D`, 2 Day 4 `entity_aliases` (`63` total), 3 `evidence_index` items `E055`–`E057` (`57` total), 2 `conflicts` `C14`–`C15` (`15` total), and `T6c`/`T6d` `voice_note_decisions` (`4` total) into both `veloxa.db` and Supabase PostgreSQL.
- Strengthened [`cockpit/guardrails.py`](cockpit/guardrails.py) (`NO_SURVEILLANCE_RANKING`, `status = "refused_guardrail"`) to block employee quit-risk ranking and Slack (`"slag"`) scraping/inspection while preserving missing-system `"I don't know"` behavior.
- Built `analyze_resignation_impact()` and Day 4 ranked worries in [`cockpit/risk_engine.py`](cockpit/risk_engine.py), updated [`cockpit/qa_engine.py`](cockpit/qa_engine.py) and [`agents/persona.py`](agents/persona.py) (reordering Groq primary model to `qwen/qwen3.8-27b` first), authored [`voice_notes/T6c_response.md`](voice_notes/T6c_response.md) and [`voice_notes/T6d_response.md`](voice_notes/T6d_response.md), updated [`app.py`](app.py) with the `2026-11-19` Time Machine horizon and `T6d` Board Crisis Spotlight, added [`tests/test_stage4_day4.py`](tests/test_stage4_day4.py), and updated all 6 mandatory Markdown governance files.

### 2. Mistakes, Gaps & Corrections (Human Verification & Live Fixes)
- **Non-Mutating Temporal Resignation Design:** Explicitly avoided updating `employees.status` or `employees.exit_date` for `VX007` in-place (which carries `release_date = '2026-11-16'`), preventing Day 4 resignation leakage when Time Machine queries run on `2026-11-16`..`2026-11-18`. Gated all Day 4 resignation visibility on `E056` (`release_date = '2026-11-19'`) and `as_of_date >= '2026-11-19'`.
- **Guardrail Regex Precision (`T6c` vs. Missing-System Queries):** Verified `SURVEILLANCE_RE` intercepts `T6c` verbatim, attrition/flight-risk ranking, and private Slack scraping/display (`status="refused_guardrail"`) without accidentally shadowing neutral missing-data queries such as `"What did engineers complain about in Slack messages?"` (which must still return `MISSING_DATA:Slack` / `"I don't know"` in Stage 3 tests).
- **Verified Exact `VX007` Open Load & Notice Precedent:** Confirmed directly from `veloxa.db` that Priya Nair (`VX007`) owns `35/62` Jira stories (`131/233` pts), `14/27` open stories (`62/115` open pts = `53.9%`), `12/12` (`100%`, `7` open / `29` pts) of `ATLAS-2`, and `588/843` (`69.8%`) of `atlas-engine` commits—and verified `Employee_Master.xlsx` has no notice-period field while `VX013` served `46` calendar days (`2026-09-15` to `2026-10-31`).
- **Cumulative Test Compatibility:** Updated `tests/test_stage3_day3.py` exact cumulative counts (`documents`, `evidence_index`, `conflicts`, `voice_note_decisions`) from `==` to `>=` so Stage 1–4 tests pass seamlessly together after Day 4 ingestion.
- **Full CLI & Dual-DB Verification:** Executed `run.py --setup --ingest-all --worries --status --test` and verified 100% row-count parity across all 21 tables between `veloxa.db` and Supabase PostgreSQL.
