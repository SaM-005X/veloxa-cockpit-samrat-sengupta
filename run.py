"""Single-command CLI runner for Veloxa CXO Cockpit."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from db.database import DatabaseManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Veloxa CXO Cockpit CLI Runner")
    parser.add_argument("--setup", action="store_true", help="Initialize SQLite & Supabase schema")
    parser.add_argument("--ingest-day1", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run Day 1 ingestion from DATA_DIR")
    parser.add_argument("--ingest-day2", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run Day 2 ingestion from DATA_DIR")
    parser.add_argument("--ingest-all", metavar="DATA_DIR", nargs="?", const=os.getenv("VELOXA_DATA_DIR", ""), help="Run all available ingestion stages (Day 1 + Day 2) from DATA_DIR")
    parser.add_argument("--worries", action="store_true", help="Display Top Ranked Strategic Worries (per T6a)")
    parser.add_argument("--as-of", default="2026-11-17", help="Point-in-Time as-of date (YYYY-MM-DD, default: 2026-11-17)")
    parser.add_argument("--status", action="store_true", help="Show database backend & table counts")
    parser.add_argument("--test", action="store_true", help="Run pytest automated suite")
    args = parser.parse_args()

    actions_specified = [
        args.setup,
        args.ingest_day1 is not None,
        args.ingest_day2 is not None,
        args.ingest_all is not None,
        args.worries,
        args.status,
        args.test,
    ]
    if not any(actions_specified):
        args.setup = True
        args.status = True

    db = DatabaseManager()

    if args.setup:
        res = db.init_schema(sync_postgres=True)
        print("Schema initialization:", json.dumps(res, indent=2))

    if args.ingest_all is not None:
        data_dir = args.ingest_all or os.getenv("VELOXA_DATA_DIR", "")
        if not data_dir:
            print("Skipping ingestion: no DATA_DIR passed and VELOXA_DATA_DIR is unset.")
        else:
            from ingest.day1_loader import ingest_day1
            from ingest.day2_loader import ingest_day2

            print(f"Executing Ingest-All up to Stage 2 from {data_dir}...")
            res1 = ingest_day1(data_dir, db=db)
            print("Day 1 ingestion:", json.dumps(res1, indent=2))
            res2 = ingest_day2(data_dir, db=db)
            print("Day 2 ingestion:", json.dumps(res2, indent=2))

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

    if args.worries:
        from cockpit.risk_engine import format_worries_cli, get_ranked_worries

        worries_data = get_ranked_worries(db=db, as_of_date=args.as_of, top_n=3)
        print(format_worries_cli(worries_data))

    if args.status:
        print("SQLite database counts:", json.dumps(db.table_counts(), indent=2))
        if db.postgres_enabled:
            print("Supabase Postgres counts:", json.dumps(db.table_counts(use_postgres=True), indent=2))
        else:
            print("Supabase Postgres counts: skipped (DATABASE_URL not set in .env)")

    if args.test:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
        return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
