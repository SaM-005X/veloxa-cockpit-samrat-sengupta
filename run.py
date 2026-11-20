"""Single-command CLI runner for Veloxa CXO Cockpit."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from db.database import DatabaseManager
from db.seed import DEFAULT_SEED_PATH, ensure_populated, export_seed_snapshot, load_seed_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Veloxa CXO Cockpit CLI Runner")
    parser.add_argument("--setup", action="store_true", help="Initialize SQLite & Supabase schema")
    parser.add_argument("--seed", action="store_true", help="Hydrate local SQLite from portable offline seed")
    parser.add_argument("--export-seed", action="store_true", help="Export sanitized SQLite snapshot to data/seed/veloxa_seed.json")
    parser.add_argument("--ingest-day1", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run Day 1 ingestion from DATA_DIR")
    parser.add_argument("--ingest-day2", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run Day 2 ingestion from DATA_DIR")
    parser.add_argument("--ingest-day3", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run Day 3 ingestion from DATA_DIR")
    parser.add_argument("--ingest-day4", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run Day 4 ingestion from DATA_DIR")
    parser.add_argument("--ingest-all", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run all available ingestion stages (or hydrate portable offline seed if raw packs are absent)")
    parser.add_argument("--worries", action="store_true", help="Display Top Ranked Strategic Worries (per T6a)")
    parser.add_argument("--impact", metavar="VX_ID", nargs="?", const="VX007", help="Run Point-in-Time resignation & SPOF impact analysis (default: VX007)")
    parser.add_argument("--ask", metavar="QUESTION", help="Ask the grounded CEO Q&A Cockpit a strategic question")
    parser.add_argument("--interview", nargs=2, metavar=("VX_ID", "QUESTION"), help="Conduct a 1-on-1 Point-in-Time interview with one of the 14 colleague personas")
    parser.add_argument("--panel", nargs=2, metavar=("DEPT_OR_IDS", "QUESTION"), help="Run a multi-agent panel cross-check (e.g. Engineering or VX006,VX003)")
    parser.add_argument("--as-of", default="2026-11-19", help="Point-in-Time as-of date (YYYY-MM-DD, default: 2026-11-19)")
    parser.add_argument("--status", action="store_true", help="Show database backend & table counts")
    parser.add_argument("--test", action="store_true", help="Run pytest automated suite")
    parser.add_argument("--ui", action="store_true", help="Launch Streamlit executive Cockpit UI")
    args = parser.parse_args()

    actions_specified = [
        args.setup,
        args.seed,
        args.export_seed,
        args.ingest_day1 is not None,
        args.ingest_day2 is not None,
        args.ingest_day3 is not None,
        args.ingest_day4 is not None,
        args.ingest_all is not None,
        args.worries,
        args.impact is not None,
        args.ask is not None,
        args.interview is not None,
        args.panel is not None,
        args.status,
        args.test,
        args.ui,
    ]
    if not any(actions_specified):
        args.setup = True
        args.status = True

    db = DatabaseManager()

    if args.setup:
        res = db.init_schema(sync_postgres=True)
        print("Schema initialization:", json.dumps(res, indent=2))

    explicit_ingest = any([
        args.seed,
        args.ingest_all is not None,
        args.ingest_day1 is not None,
        args.ingest_day2 is not None,
        args.ingest_day3 is not None,
        args.ingest_day4 is not None,
    ])

    if args.seed:
        seed_res = load_seed_snapshot(db=db, seed_path=DEFAULT_SEED_PATH, sync_postgres=False, force=True)
        print("Portable seed hydration:", json.dumps(seed_res, indent=2))

    if args.ingest_all is not None:
        data_dir = (args.ingest_all or os.getenv("VELOXA_DATA_DIR", "")).strip()
        if data_dir and (Path(data_dir) / "Day1_Mon_16Nov").is_dir():
            from ingest.day1_loader import ingest_day1
            from ingest.day2_loader import ingest_day2
            from ingest.day3_loader import ingest_day3
            from ingest.day4_loader import ingest_day4

            print(f"Executing Ingest-All up to Stage 4 from {data_dir}...")
            res1 = ingest_day1(data_dir, db=db)
            print("Day 1 ingestion:", json.dumps(res1, indent=2))
            res2 = ingest_day2(data_dir, db=db)
            print("Day 2 ingestion:", json.dumps(res2, indent=2))
            res3 = ingest_day3(data_dir, db=db)
            print("Day 3 ingestion:", json.dumps(res3, indent=2))
            res4 = ingest_day4(data_dir, db=db)
            print("Day 4 ingestion:", json.dumps(res4, indent=2))
        elif DEFAULT_SEED_PATH.is_file():
            print(f"Raw release packs not mounted; hydrating veloxa.db from portable offline seed ({DEFAULT_SEED_PATH.relative_to(Path(__file__).resolve().parent)})...")
            seed_res = load_seed_snapshot(db=db, seed_path=DEFAULT_SEED_PATH, sync_postgres=False, force=True)
            print("Portable seed hydration:", json.dumps(seed_res, indent=2))
        else:
            print("Skipping ingestion: no DATA_DIR passed, VELOXA_DATA_DIR is unset, and no portable seed found.")

    else:
        if args.ingest_day1 is not None:
            if not args.ingest_day1:
                print("Skipping Day 1 ingestion: no DATA_DIR passed and VELOXA_DATA_DIR is unset.")
            else:
                from ingest.day1_loader import ingest_day1

                res = ingest_day1(args.ingest_day1, db=db)
                print("Day 1 ingestion:", json.dumps(res, indent=2))

        if args.ingest_day2 is not None:
            if not args.ingest_day2:
                print("Skipping Day 2 ingestion: no DATA_DIR passed and VELOXA_DATA_DIR is unset.")
            else:
                from ingest.day2_loader import ingest_day2

                res = ingest_day2(args.ingest_day2, db=db)
                print("Day 2 ingestion:", json.dumps(res, indent=2))

        if args.ingest_day3 is not None:
            if not args.ingest_day3:
                print("Skipping Day 3 ingestion: no DATA_DIR passed and VELOXA_DATA_DIR is unset.")
            else:
                from ingest.day3_loader import ingest_day3

                res = ingest_day3(args.ingest_day3, db=db)
                print("Day 3 ingestion:", json.dumps(res, indent=2))

        if args.ingest_day4 is not None:
            if not args.ingest_day4:
                print("Skipping Day 4 ingestion: no DATA_DIR passed and VELOXA_DATA_DIR is unset.")
            else:
                from ingest.day4_loader import ingest_day4

                res = ingest_day4(args.ingest_day4, db=db)
                print("Day 4 ingestion:", json.dumps(res, indent=2))

    if args.export_seed:
        exp_res = export_seed_snapshot(db=db, output_path=DEFAULT_SEED_PATH)
        print("Portable seed export:", json.dumps(exp_res, indent=2))

    if not explicit_ingest and not args.export_seed and any([
        args.setup,
        args.worries,
        args.impact is not None,
        args.ask is not None,
        args.interview is not None,
        args.panel is not None,
        args.status,
        args.ui,
    ]):
        ensure_populated(db=db)

    if args.worries:
        from cockpit.risk_engine import format_worries_cli, get_ranked_worries

        worries_data = get_ranked_worries(db=db, as_of_date=args.as_of, top_n=3)
        print(format_worries_cli(worries_data))

    if args.impact is not None:
        from cockpit.risk_engine import analyze_resignation_impact

        impact_res = analyze_resignation_impact(db=db, employee_id=args.impact, as_of_date=args.as_of)
        print(json.dumps(impact_res, indent=2, ensure_ascii=False))

    if args.ask is not None:
        from cockpit.qa_engine import ask_cockpit

        qa_res = ask_cockpit(db=db, question=args.ask, as_of_date=args.as_of)
        print(json.dumps(
            {k: v for k, v in qa_res.items() if k != "citation_records"},
            indent=2,
            ensure_ascii=False,
        ))

    if args.interview is not None:
        from agents.persona import interview_agent

        emp_id, question = args.interview
        iv_res = interview_agent(db=db, emp_id=emp_id, question=question, as_of_date=args.as_of)
        print(json.dumps(iv_res, indent=2, ensure_ascii=False))

    if args.panel is not None:
        from agents.persona import panel_interview

        target, question = args.panel
        panel_res = panel_interview(db=db, target_ids_or_dept=target, question=question, as_of_date=args.as_of)
        print(json.dumps(panel_res, indent=2, ensure_ascii=False))

    if args.status:
        print("SQLite database counts:", json.dumps(db.table_counts(), indent=2))
        if db.postgres_enabled:
            print("Supabase Postgres counts:", json.dumps(db.table_counts(use_postgres=True), indent=2))
        else:
            print("Supabase Postgres counts: skipped (DATABASE_URL not set in .env)")

    if args.test:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
        if proc.returncode != 0:
            return proc.returncode

    if args.ui:
        proc = subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"], check=False)
        return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
