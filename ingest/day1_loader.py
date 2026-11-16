"""Day 1 ingestion pipeline (`Day1_Mon_16Nov`, release_date = 2026-11-16).

Parses raw Day 1 spreadsheets, PDFs, Word transcripts, and `.eml` files from
`VELOXA_DATA_DIR` (or `--data-dir`) into the local SQLite mirror (`veloxa.db`)
and optionally Supabase PostgreSQL (`DATABASE_URL`).
"""

from __future__ import annotations

import email
import json
import os
from email import policy
from pathlib import Path
from typing import Any

from db.database import DatabaseManager
from ingest.temporal import RELEASE_DATES

DAY1_TAG = "Day1_Mon_16Nov"
DAY1_RELEASE_DATE = RELEASE_DATES[DAY1_TAG]

# Agent roster scope (14 target colleagues across Engineering, Finance, People & Ops, Marketing)
AGENT_DEPARTMENTS = {"Engineering", "Finance", "People & Ops", "People", "HR", "Marketing"}


def _normalize_col(col: Any) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


def _find_day1_root(data_dir: Path) -> Path:
    """Locate Day 1 files whether `data_dir` points to root pack or Day1 folder."""
    if (data_dir / DAY1_TAG).is_dir():
        return data_dir / DAY1_TAG
    return data_dir


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes
    )


def _extract_docx_text(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    for tbl in doc.tables:
        for row in tbl.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        txt = (page.extract_text() or "").strip()
        if txt:
            pages.append((idx, txt))
    return pages


def _parse_eml(path: Path) -> dict[str, str]:
    raw_bytes = path.read_bytes()
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_content()
                break
    else:
        body = msg.get_content() if hasattr(msg, "get_content") else str(msg.get_payload())

    return {
        "email_id": path.stem,
        "sender_raw": str(msg.get("From", "")).strip(),
        "recipients_raw": str(msg.get("To", "")).strip(),
        "cc_raw": str(msg.get("Cc", "")).strip(),
        "subject": str(msg.get("Subject", "")).strip(),
        "sent_at": str(msg.get("Date", "")).strip(),
        "body_text": str(body).strip(),
        "source_file": path.name,
    }


def _pick(row: dict[str, Any], *candidates: str, default: Any = "") -> Any:
    for key in candidates:
        if key in row and row[key] not in (None, "", "nan", "NaN"):
            return row[key]
    return default


def ingest_day1(data_dir: str | Path, db: DatabaseManager | None = None) -> dict[str, Any]:
    """Ingest Day 1 files from `data_dir` into SQLite and (if set) Supabase Postgres."""
    db = db or DatabaseManager()
    db.init_schema(sync_postgres=True)

    root = _find_day1_root(Path(data_dir).expanduser().resolve())
    if not root.exists():
        raise FileNotFoundError(f"Day 1 data directory not found: {root}")

    files_loaded = 0
    records_loaded = 0

    import pandas as pd

    employees_rows: list[tuple[Any, ...]] = []
    gl_rows: list[tuple[Any, ...]] = []
    payroll_sum_rows: list[tuple[Any, ...]] = []
    payroll_res_rows: list[tuple[Any, ...]] = []
    alias_rows: list[tuple[Any, ...]] = []
    evidence_rows: list[tuple[Any, ...]] = []
    email_rows: list[tuple[Any, ...]] = []
    doc_rows: list[tuple[Any, ...]] = []

    # 1. Spreadsheets (.xlsx)
    for xlsx_path in _iter_files(root, (".xlsx",)):
        fname = xlsx_path.name
        xl = pd.ExcelFile(xlsx_path)
        files_loaded += 1

        if "employee_master" in fname.lower():
            df = pd.read_excel(xlsx_path, sheet_name=xl.sheet_names[0]).fillna("")
            df.columns = [_normalize_col(c) for c in df.columns]
            for r in df.to_dict(orient="records"):
                emp_id = str(_pick(r, "employee_id", "emp_id", "id", "entity_id")).strip()
                if not emp_id:
                    continue
                dept = str(_pick(r, "department", "dept")).strip()
                status = str(_pick(r, "status", default="Active")).strip()
                emp_type = str(_pick(r, "employment_type", "type", default="FTE")).strip()
                is_agent = int(dept in AGENT_DEPARTMENTS and emp_id.startswith("VX") and emp_id != "VX001")
                employees_rows.append((
                    emp_id,
                    str(_pick(r, "full_name", "name", "employee_name")).strip(),
                    str(_pick(r, "email", "work_email")).strip(),
                    dept,
                    str(_pick(r, "title", "role", "designation")).strip(),
                    str(_pick(r, "manager_id", "reports_to", "manager")).strip(),
                    str(_pick(r, "join_date", "joining_date", "start_date")).strip(),
                    str(_pick(r, "exit_date", "last_working_day")).strip(),
                    str(_pick(r, "location", "city")).strip(),
                    emp_type,
                    status,
                    is_agent,
                    DAY1_RELEASE_DATE,
                ))

        elif "gl_export" in fname.lower():
            df = pd.read_excel(xlsx_path, sheet_name=xl.sheet_names[0]).fillna("")
            df.columns = [_normalize_col(c) for c in df.columns]
            for idx, r in enumerate(df.to_dict(orient="records"), start=1):
                voucher = str(_pick(r, "voucher_id", "jv_no", "journal_id", "id", default=f"GL-{idx:04d}")).strip()
                txn_date = str(_pick(r, "txn_date", "date", "posting_date")).strip()
                amount_raw = _pick(r, "amount_inr", "amount", "debit", "net_amount", default=0)
                try:
                    amount = float(str(amount_raw).replace(",", "").strip() or 0)
                except ValueError:
                    amount = 0.0
                vendor = str(_pick(r, "vendor_name", "vendor", "party")).strip()
                gl_rows.append((
                    voucher,
                    txn_date,
                    txn_date[:10] if txn_date else "",
                    str(_pick(r, "account_code", "gl_code", "account")).strip(),
                    str(_pick(r, "account_name", "category")).strip(),
                    str(_pick(r, "cost_center", "department", "cc")).strip(),
                    vendor,
                    vendor,
                    str(_pick(r, "description", "narration", "memo")).strip(),
                    amount,
                    str(_pick(r, "entered_by", "created_by", "preparer")).strip(),
                    fname,
                    DAY1_RELEASE_DATE,
                ))

        elif "payroll_register" in fname.lower():
            for sheet in xl.sheet_names:
                df = pd.read_excel(xlsx_path, sheet_name=sheet).fillna("")
                df.columns = [_normalize_col(c) for c in df.columns]
                records = df.to_dict(orient="records")
                dept_totals: dict[str, dict[str, Any]] = {}
                for r in records:
                    emp_id = str(_pick(r, "employee_id", "emp_id", "id")).strip()
                    if not emp_id:
                        continue
                    period = str(_pick(r, "period_month", "month", "period", default=sheet)).strip()
                    dept = str(_pick(r, "department", "dept", default="All")).strip()
                    gross = float(str(_pick(r, "gross_inr", "gross_salary", "gross", default=0)).replace(",", "") or 0)
                    net = float(str(_pick(r, "net_inr", "net_salary", "net_pay", default=0)).replace(",", "") or 0)
                    days_paid = _pick(r, "days_paid", "paid_days", default=None)
                    days_month = _pick(r, "days_in_month", "total_days", default=None)
                    preparer = str(_pick(r, "prepared_by", "run_by")).strip()
                    payroll_res_rows.append((
                        period,
                        emp_id,
                        float(days_paid) if days_paid not in ("", None) else None,
                        int(float(days_month)) if days_month not in ("", None) else None,
                        gross,
                        net,
                        preparer,
                        str(_pick(r, "anomaly_flag", "notes", default="")).strip(),
                        f"{fname}#{sheet}",
                        DAY1_RELEASE_DATE,
                    ))
                    bucket = dept_totals.setdefault(
                        f"{period}::{dept}",
                        {"period": period, "dept": dept, "hc": 0, "gross": 0.0, "net": 0.0, "prep": preparer},
                    )
                    bucket["hc"] += 1
                    bucket["gross"] += gross
                    bucket["net"] += net

                for b in dept_totals.values():
                    payroll_sum_rows.append((
                        b["period"],
                        b["dept"],
                        b["hc"],
                        b["gross"],
                        b["net"],
                        b["prep"],
                        "Aggregated from Payroll Register (individual rows restricted per CFO T2 rule)",
                        f"{fname}#{sheet}",
                        DAY1_RELEASE_DATE,
                    ))

        elif "entity_resolution" in fname.lower():
            df = pd.read_excel(xlsx_path, sheet_name=xl.sheet_names[0]).fillna("")
            df.columns = [_normalize_col(c) for c in df.columns]
            for r in df.to_dict(orient="records"):
                alias_txt = str(_pick(r, "alias_text", "alias", "raw_name")).strip()
                canon_id = str(_pick(r, "canonical_id", "entity_id", "id")).strip()
                if alias_txt and canon_id:
                    alias_rows.append((
                        alias_txt,
                        canon_id,
                        str(_pick(r, "entity_type", "type", default="person")).strip(),
                        str(_pick(r, "canonical_name", "name", default="")).strip(),
                        str(_pick(r, "notes", default="")).strip(),
                        DAY1_RELEASE_DATE,
                    ))

        elif "evidence_index" in fname.lower():
            df = pd.read_excel(xlsx_path, sheet_name=xl.sheet_names[0]).fillna("")
            df.columns = [_normalize_col(c) for c in df.columns]
            for idx, r in enumerate(df.to_dict(orient="records"), start=1):
                ev_id = str(_pick(r, "evidence_id", "id", default=f"E-TMPL-{idx:03d}")).strip()
                fact = str(_pick(r, "fact_text", "fact", "claim", "summary")).strip()
                if not fact:
                    continue
                evidence_rows.append((
                    ev_id,
                    str(_pick(r, "source_file", "source", default=fname)).strip(),
                    str(_pick(r, "source_type", "type", default="export")).strip(),
                    str(_pick(r, "location", "ref", default="sheet1")).strip(),
                    fact,
                    json.dumps([str(_pick(r, "entities", default=""))]),
                    str(_pick(r, "event_date", default="")).strip(),
                    DAY1_RELEASE_DATE,
                    str(_pick(r, "reliability", default="Medium")).strip(),
                    str(_pick(r, "conflict_group_id", default="")).strip() or None,
                ))

    # 2. Emails (.eml)
    for eml_path in _iter_files(root, (".eml",)):
        files_loaded += 1
        parsed = _parse_eml(eml_path)
        email_rows.append((
            parsed["email_id"],
            parsed["sender_raw"],
            None,
            parsed["recipients_raw"],
            parsed["cc_raw"],
            parsed["subject"],
            parsed["sent_at"],
            parsed["sent_at"][:10] if parsed["sent_at"] else "",
            parsed["body_text"],
            parsed["source_file"],
            DAY1_RELEASE_DATE,
        ))

    # 3. Word Documents (.docx)
    for docx_path in _iter_files(root, (".docx",)):
        files_loaded += 1
        txt = _extract_docx_text(docx_path)
        doc_type = "transcript" if docx_path.name.startswith("T") else "brief"
        doc_rows.append((
            docx_path.stem,
            docx_path.name,
            doc_type,
            docx_path.stem,
            "full_text",
            txt,
            "",
            DAY1_RELEASE_DATE,
        ))

    # 4. PDF Documents (.pdf)
    for pdf_path in _iter_files(root, (".pdf",)):
        files_loaded += 1
        for page_num, txt in _extract_pdf_pages(pdf_path):
            doc_type = "board_update" if "board_update" in pdf_path.name.lower() else "pdf_report"
            doc_rows.append((
                f"{pdf_path.stem}_p{page_num}",
                pdf_path.name,
                doc_type,
                pdf_path.stem,
                f"page_{page_num}",
                txt,
                "",
                DAY1_RELEASE_DATE,
            ))

    # 5. Plain text README (.txt)
    for txt_path in _iter_files(root, (".txt",)):
        files_loaded += 1
        doc_rows.append((
            txt_path.stem,
            txt_path.name,
            "readme",
            txt_path.stem,
            "full_text",
            txt_path.read_text(encoding="utf-8", errors="replace").strip(),
            "",
            DAY1_RELEASE_DATE,
        ))

    # Persist into SQLite mirror
    with db.sqlite_conn() as conn:
        if employees_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO employees
                (entity_id, full_name, email, department, title, manager_id, join_date,
                 exit_date, location, employment_type, status, is_agent_persona, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                employees_rows,
            )
        if gl_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO gl_transactions
                (voucher_id, txn_date, event_date, account_code, account_name, cost_center,
                 vendor_name, canonical_vendor, description, amount_inr, entered_by,
                 source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                gl_rows,
            )
        if payroll_sum_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO payroll_summary
                (period_month, department, headcount, total_gross_inr, total_net_inr,
                 prepared_by, notes, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                payroll_sum_rows,
            )
        if payroll_res_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO payroll_restricted
                (period_month, employee_id, days_paid, days_in_month, gross_inr, net_inr,
                 prepared_by, anomaly_flag, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                payroll_res_rows,
            )
        if alias_rows:
            conn.executemany(
                """INSERT OR IGNORE INTO entity_aliases
                (alias_text, canonical_id, entity_type, canonical_name, notes, release_date)
                VALUES (?, ?, ?, ?, ?, ?)""",
                alias_rows,
            )
        if evidence_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO evidence_index
                (evidence_id, source_file, source_type, location, fact_text, entities_json,
                 event_date, release_date, reliability, conflict_group_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                evidence_rows,
            )
        if email_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO emails
                (email_id, sender_raw, sender_entity_id, recipients_raw, cc_raw, subject,
                 sent_at, event_date, body_text, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                email_rows,
            )
        if doc_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO documents
                (doc_id, source_file, doc_type, title, section_label, content_text,
                 event_date, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                doc_rows,
            )

        records_loaded = (
            len(employees_rows)
            + len(gl_rows)
            + len(payroll_sum_rows)
            + len(payroll_res_rows)
            + len(alias_rows)
            + len(evidence_rows)
            + len(email_rows)
            + len(doc_rows)
        )
        conn.execute(
            """INSERT OR REPLACE INTO ingestion_runs
            (release_tag, release_date, source_dir, files_loaded, records_loaded, status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (DAY1_TAG, DAY1_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
        )

    return {
        "release_tag": DAY1_TAG,
        "release_date": DAY1_RELEASE_DATE,
        "files_loaded": files_loaded,
        "records_loaded": records_loaded,
        "counts": {
            "employees": len(employees_rows),
            "gl_transactions": len(gl_rows),
            "payroll_summary": len(payroll_sum_rows),
            "payroll_restricted": len(payroll_res_rows),
            "entity_aliases": len(alias_rows),
            "evidence_index": len(evidence_rows),
            "emails": len(email_rows),
            "documents": len(doc_rows),
        },
        "postgres_synced": False if not db.postgres_enabled else "pending_pg_sync",
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Day 1 Veloxa release pack.")
    parser.add_argument(
        "--data-dir",
        default=os.getenv("VELOXA_DATA_DIR", ""),
        help="Path to Veloxa_Hackathon_Release_Packs or Day1_Mon_16Nov folder",
    )
    args = parser.parse_args()
    if not args.data_dir:
        raise SystemExit("Error: pass --data-dir or set VELOXA_DATA_DIR in .env")
    result = ingest_day1(args.data_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
