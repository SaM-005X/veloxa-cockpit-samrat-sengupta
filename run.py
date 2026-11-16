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
    parser.add_argument("--status", action="store_true", help="Show database backend & table counts")
    parser.add_argument("--test", action="store_true", help="Run pytest automated suite")
    args = parser.parse_args()

    if not any([args.setup, args.ingest_day1 is not None, args.status, args.test]):
        args.setup = True
        args.status = True

    db = DatabaseManager()

    if args.setup:
        res = db.init_schema(sync_postgres=True)
        print("Schema initialization:", json.dumps(res, indent=2))

    if args.ingest_day1 is not None:
        if not args.ingest_day1:
            print("Skipping Day 1 ingestion: no DATA_DIR passed and VELOXA_DATA_DIR is unset.")
        else:
            from ingest.day1_loader import ingest_day1

            res = ingest_day1(args.ingest_day1, db=db)
            print("Day 1 ingestion:", json.dumps(res, indent=2))

    if args.status:
        print("Database counts:", json.dumps(db.table_counts(), indent=2))

    if args.test:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
        return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
