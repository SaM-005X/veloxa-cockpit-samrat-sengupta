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
