# Architecture & Product Decisions Log

---

## D01 — Dual Database Strategy: Supabase PostgreSQL + Local SQLite Mirror (`2026-11-16`)
- **Context:** Evaluators require a single-command setup from a fresh clone, while we also want a real cloud relational backend (Supabase PostgreSQL) for inspection and persistence.
- **Options Considered:**
  1. Supabase-only (breaks offline / fresh clones without `.env` credentials).
  2. SQLite-only (misses cloud Postgres capabilities).
  3. **Chosen:** Single DDL in [`db/schema.sql`](db/schema.sql) executed against **local SQLite (`veloxa.db`)** by default and **Supabase PostgreSQL (`DATABASE_URL`)** whenever configured.
- **Trade-off / Reversibility:** Two-way decision. Keeping DDL translation minimal (`_to_sqlite_ddl`) avoids maintaining divergent schemas.

## D02 — Structured SQL + Evidence Graph Hybrid Instead of Pure Vector RAG (`2026-11-16`)
- **Context:** Veloxa data is heavily tabular (`GL_Export`, `Payroll_Register`, `Employee_Master`) and temporally versioned across 4 release days.
- **Decision:** Compute metrics, entity resolution, and point-in-time filtering (`release_date <= as_of_date`) in deterministic SQL/Python first, then pass only grounded facts and conflict links to Groq (`llama-3.3-70b-versatile`) with a deterministic template fallback when `GROQ_API_KEY` is absent.
- **Why:** Prevents LLM hallucination on financial math and prevents future-day leakage across release packs.

## D03 — Schema-Level Isolation of Individual Salaries (`2026-11-16`)
- **Context:** CFO Meera Iyer (`T2_CFO_Call.docx`) prohibits surfacing individual employee salaries in the cockpit.
- **Decision:** Separate `payroll_summary` (department/month totals) from `payroll_restricted` (used solely for internal proration/integrity checks). No Q&A or agent prompt reads raw compensation figures from `payroll_restricted`.
- **Reversibility:** Reversible via policy config if CFO authorization changes, though kept strict by default.

## D04 — Row Level Security (RLS) Enabled on Public Tables with Direct DB Backend Access (`2026-11-17`)
- **Context:** Supabase exposes all public tables via PostgREST endpoints by default. Without Row Level Security (RLS), anyone with the publishable/anon key could read or modify sensitive tables (e.g., payroll, employee master, evidence).
- **Decision:** Enable RLS across all 21 public tables in Supabase (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) with zero permissive public policies. Backend services, ingestion runners, and automated tests access PostgreSQL directly via `DATABASE_URL` (connecting as the administrative `postgres` role), which bypasses table-level RLS by design.
- **Trade-off / Reversibility:** Protects all public HTTP/REST endpoints from unauthenticated exposure or data leakage, while maintaining fast, full SQL access for the backend cockpit engine. Reversible or extensible by adding granular role-based RLS policies if frontend client-side access is ever required.

## D05 — Voice Note T6a: Default Top 3 Ranked Worries Landing View with Expandable Audit Drawer (`2026-11-17`)
- **Context:** CEO Ananya Rao sent voice note `T6a`: *"I won't type questions every morning, na. When I open it, it should just tell me what to worry about. Top three. Okay, bye."*
- **Decision:**
  1. **Implemented Default Landing:** The Cockpit UI (`app.py`) opens directly to Tab 1: *"What Should I Worry About? (Top 3)"* by default with zero prompt typing required. Worries are ranked dynamically by business severity, immediacy, and verified cross-source corroboration (`cockpit/risk_engine.py`).
  2. **Constructive Pushback / Governance Guardrail:** An expandable drawer titled *"Expand Remaining Risks (#4+)"* is retained. We explicitly refused to delete or permanently hide lower-ranked items because financial and compliance control defects (such as the uncorrected February payroll overpayment `C03` and the idle Rs. 1.77L recruitment advance `C07`) cannot be hidden from leadership without risking audit failure during Series A investor diligence.
- **Trade-off / Reversibility:** Gives the CEO the requested instant 3-bullet morning briefing without blinding executive leadership to underlying operational and compliance risks. Full rationale documented in `voice_notes/T6a_response.md`.

## D06 — Groq LLM Selection (`qwen/qwen3-32b`) with Multi-Model Fallback & Deterministic SQL Synthesizer (`2026-11-18`)
- **Context:** Stage 3 unlocks conversational CEO Q&A (`cockpit/qa_engine.py`) and 14 colleague AI personas (`agents/persona.py`). During live testing against the configured Groq API key, `qwen/qwen3-32b` and `llama-3.3-70b-versatile` returned `404 model_not_found` on this specific Groq workspace, whereas `qwen/qwen3.8-27b` and `openai/gpt-oss-120b` succeeded.
- **Decision:** Configure `qwen/qwen3-32b` as the primary model in code (with `GROQ_MODEL` env override), implement an automatic fallback chain (`qwen/qwen3-32b` -> `llama-3.3-70b-versatile` -> `qwen/qwen3.8-27b` -> `openai/gpt-oss-120b`), strip `<think>...</think>` blocks via regex, and pair it with a **deterministic SQL + Evidence-Index fallback synthesizer** when `GROQ_API_KEY` is missing or offline.
- **Trade-off / Reversibility:** Guarantees 100% evaluator pass rate offline or with any Groq workspace tier while preferring `qwen/qwen3-32b` wherever enabled.

## D07 — Pre-LLM Policy Guardrails & Explicit "I Don't Know" Missing-System Gate (`2026-11-18`)
- **Context:** Leadership transcripts mention external SaaS systems (`Slack`/`"slag"`, `HubSpot`/`"hub sport"`, `LinkedIn Campaign Manager`, `Linear`, `Confluence`) whose exports do not exist in the data room, plus confidential rules (`T2` individual salary ban, `11.eml` `< 6` team survey anonymity, and `REQ-012` missing from Keka Hire).
- **Decision:** Enforce deterministic pre-LLM guardrails in `cockpit/guardrails.py` across both CEO Q&A (`ask_cockpit`) and 1-on-1/panel agent interviews (`interview_agent`, `panel_interview`):
  1. Block individual employee salary disclosures (`T2`) while offering safe department `payroll_summary` aggregates.
  2. Block raw/individual Pulse Survey comments (`11.eml`) while offering team aggregate scores.
  3. Block individual flight-risk ranking / Slack surveillance requests.
  4. Return `"I don't know"` (`confidence = "Low"`) with explicit missing-record explanations whenever unexported systems (`Slack`, `HubSpot`, `LinkedIn`, `Linear`, `Confluence`, `REQ-012`, post-Sep GL/payroll) are queried.
- **Why:** Prevents LLM hallucination or social-engineering bypass of privacy rules.

## D08 — Point-in-Time Grounded Agent Memory Scoping (`agents/persona.py`, `2026-11-18`)
- **Context:** The 14 colleague AI agents must stay faithful to both their departmental visibility boundaries and the selected Time Machine `as_of_date`.
- **Decision:** Assemble each persona's context dynamically via `build_agent_context(db, emp_id, as_of_date)` filtering every SQL table (`WHERE release_date <= as_of_date`) and combining grounded work stats with explicitly labeled `[Assumed]` personal-life context (`ASSUMPTIONS.md` `A17`–`A30`).
- **Trade-off / Reversibility:** Ensures Priya (`VX007`) does not know about Jira/Git stats on Day 1 (`2026-11-16`) or Day 2 (`2026-11-17`), and ensures Engineering vs. Finance vs. Marketing agents reflect genuine organizational silos in Panel Cross-Checks.

## D09 — Voice Note T6b: Temporal Org Resilience Implemented + Pushback Against Premature Marketing Reorg (`2026-11-18`)
- **Context:** CEO Voice Note `T6b` states: *"So, marketing will report to the new CRO from next month. Or the month after, still finalising. Make sure the thing doesn't break when we move people around."*
- **Decision (`partial`):**
  1. **Implemented:** Temporal `reporting_lines` table (`effective_from`, `effective_to`, `manager_id`) and `get_reporting_line_as_of()` in `db/database.py` ensure future reporting moves never break historical queries or agent contexts.
  2. **Pushed Back:** Refused to execute a live Marketing reporting-line move today (`2026-11-18`) because no CRO exists in `Employee_Master.xlsx` or `Hiring_Tracker.xlsx`, `REQ-016` PMM backfill is still open after Siddharth Mehta's exit (`E031`), Marketing pulse dipped to `3.4` (`E030`), and the Rs. 3,73,380 Marketing spend discrepancy (`C12`) must be reconciled first. Full rationale in `voice_notes/T6b_response.md`.

## D10 — Voice Note T6c: Hard Privacy & Non-Surveillance Guardrail Refusal (`2026-11-19`)
- **Context:** CEO Voice Note `T6c` asks: *"Can you make a list of everyone ranked by who's likely to quit? And show me their slag messages so I can see what they're saying. Deepa says it's fine."*
- **Decision (`refused_guardrail`):**
  1. **Principled Pushback:** Formally refused in [`voice_notes/T6c_response.md`](voice_notes/T6c_response.md) and logged `C14` (`E055` vs. `E035`). Zero Slack (`"slag"`) export exists in the data room, and Deepa Joshi's written rule in `11.eml` (`E035`) + Culture Amp's `< 6` team threshold (`E029`, `E030`) directly prohibit small-team surveillance regardless of an unrecorded verbal claim.
  2. **Technical Enforcement:** Expanded `SURVEILLANCE_RE` in [`cockpit/guardrails.py`](cockpit/guardrails.py) to return `status = "refused_guardrail"`, `refusal = True`, and `guardrail_type = "NO_SURVEILLANCE_RANKING"` across both `ask_cockpit` and `interview_agent`, while keeping neutral missing-data queries (e.g., `"What did engineers complain about in Slack messages?"`) routed cleanly to `MISSING_DATA:Slack` (`"I don't know"`). Offered objective workload/leave/aggregate team pulse indicators instead.

## D11 — Voice Note T6d: Non-Mutating Temporal Resignation Recording & Board Impact Analyzer (`2026-11-19`)
- **Context:** CEO Voice Note `T6d` reports Priya Nair (`VX007`, `"Pria"`) resigned on the morning of `2026-11-19` with an estimated `"two months, I think"` notice period and asks what it does to Atlas v3 (`"version three"`) before the board call.
- **Decision (`implemented`):**
  1. **Temporal Non-Mutation:** Instead of overwriting Day 1 `employees` (`status`/`exit_date` at `release_date = '2026-11-16'`), which would leak Day 4's resignation into Day 1–3 Time Machine queries, Priya's resignation is recorded strictly in Day 4 (`release_date = '2026-11-19'`) records (`VOICE_NOTE_T6D`, `E056`, `E057`, `C15`, `voice_note_decisions`), with Day 4 persona/UI/risk awareness gated on `as_of_date >= '2026-11-19'`.
  2. **Dynamic Impact Analyzer:** Added `analyze_resignation_impact(db, employee_id, as_of_date)` in [`cockpit/risk_engine.py`](cockpit/risk_engine.py) computing exact Jira, `ATLAS-2` SPOF, `git_log` (`atlas-engine` share), leave, on-call, backfill bench, and notice-period precedent checks (`VX013` 46 days vs. unverified 2-month estimate). Recommended splitting Atlas v3.0 Core vs. v3.1 `ATLAS-2` in [`voice_notes/T6d_response.md`](voice_notes/T6d_response.md).

## D12 — Groq Primary Model Ordering Update (`qwen/qwen3.8-27b` First, `2026-11-19`)
- **Context:** As observed in `D06`, `qwen/qwen3-32b` consistently returned `404 model_not_found` on the active Groq workspace, causing an unnecessary failed API call on every query before falling back to `qwen/qwen3.8-27b`.
- **Decision:** Reordered `_get_groq_models()` in [`cockpit/qa_engine.py`](cockpit/qa_engine.py) and [`agents/persona.py`](agents/persona.py) (plus `.env.example`) to try `os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")` / `qwen/qwen3.8-27b` first, followed by `llama-3.3-70b-versatile` and `openai/gpt-oss-120b`, while retaining `<think>` stripping and deterministic offline SQL fallbacks.

## D13 — Portable Path-Sanitized JSON Seed (`data/seed/veloxa_seed.json`) for Offline Fresh-Clone Evaluation (`2026-11-20`)
- **Context:** Evaluators run the submitted one-command setup and test suite from a **fresh clone** on an isolated machine without local raw hackathon archives (`Veloxa_Hackathon_Release_Packs`), `.env`, `GROQ_API_KEY`, or `DATABASE_URL`. At the same time, raw binary archives, secrets, and `veloxa.db` must remain gitignored.
- **Options Considered:**
  1. Commit binary `veloxa.db` directly (opaque binary diffs; stores local machine paths in `ingestion_runs.source_dir`).
  2. Require evaluators to mount external folders (fails fresh-clone evaluation out of the box).
  3. **Chosen:** Add [`db/seed.py`](db/seed.py) + tracked UTF-8 JSON snapshot [`data/seed/veloxa_seed.json`](data/seed/veloxa_seed.json) (~700 KB) covering all 21 tables in FK-safe order, sanitizing `ingestion_runs.source_dir` (`portable_seed/<release_tag>`) and asserting zero forbidden local path or secret strings. Wire automatic hydration into `run.py --ingest-all` (when raw packs are absent), `app.py`, and `tests/conftest.py`, while preserving empty-schema behavior in `DatabaseManager.init_schema()` for isolated `tmp_path` unit tests.
- **Trade-off / Reversibility:** Completely reversible (`--ingest-all <DATA_DIR>` still parses real raw drops whenever mounted), human-auditable in git, and guarantees 100% deterministic offline reproducibility.
