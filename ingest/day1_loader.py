"""Day 1 ingestion pipeline (`Day1_Mon_16Nov`, release_date = 2026-11-16).

Parses raw Day 1 spreadsheets, PDFs, Word transcripts, and `.eml` files from
`VELOXA_DATA_DIR` (or `--data-dir`) into the local SQLite mirror (`veloxa.db`)
and optionally Supabase PostgreSQL (`DATABASE_URL`).
"""

from __future__ import annotations

import email
import json
import os
import re
from datetime import date, datetime
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from db.database import DatabaseManager
from ingest.temporal import RELEASE_DATES

DAY1_TAG = "Day1_Mon_16Nov"
DAY1_RELEASE_DATE = RELEASE_DATES[DAY1_TAG]

# Agent roster scope (14 target colleagues across Engineering, Finance, People & Ops, Marketing)
AGENT_DEPARTMENTS = {"Engineering", "Finance", "People & Ops", "People", "HR", "Marketing"}

MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


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


def _to_iso_date(val: Any) -> str:
    """Normalize spreadsheet dates/timestamps/strings to YYYY-MM-DD."""
    if val in (None, "", "nan", "NaN", "NaT"):
        return ""
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, date):
        return val.isoformat()
    text = str(val).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return ""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return text[:10]


def _normalize_month(val: Any) -> str:
    """Normalize 'Jan-2026' or '2026-01' to 'YYYY-MM'."""
    text = str(val).strip()
    if re.match(r"^\d{4}-\d{2}$", text):
        return text
    m = re.match(r"^([A-Za-z]{3})[-/](\d{4})$", text)
    if m:
        mon = MONTH_MAP.get(m.group(1).lower())
        if mon:
            return f"{m.group(2)}-{mon}"
    return text


def _parse_email_iso_date(sent_at: str) -> str:
    """Extract YYYY-MM-DD from RFC 2822 or ISO date header."""
    if not sent_at:
        return ""
    try:
        dt = parsedate_to_datetime(sent_at)
        return dt.date().isoformat()
    except (TypeError, ValueError):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", sent_at.strip())
        return m.group(1) if m else ""


def _read_xlsx_sheet(
    xlsx_path: Path,
    sheet_name: str,
    header_markers: set[str],
) -> list[dict[str, Any]]:
    """Read an Excel sheet, auto-detecting header row past banner/preamble lines."""
    import pandas as pd

    raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None, dtype=object)
    header_idx = 0
    for idx in range(min(10, len(raw))):
        norm_cells = {_normalize_col(v) for v in raw.iloc[idx].tolist() if pd.notna(v)}
        if norm_cells & header_markers:
            header_idx = idx
            break

    headers = [_normalize_col(v) if pd.notna(v) else f"col_{i}" for i, v in enumerate(raw.iloc[header_idx].tolist())]
    body = raw.iloc[header_idx + 1 :].copy()
    body.columns = headers
    body = body.dropna(how="all").fillna("")
    return body.to_dict(orient="records")


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


def _extract_email_addr(raw_header: str) -> str:
    m = re.search(r"<([^>]+)>", raw_header)
    if m:
        return m.group(1).strip().lower()
    return raw_header.strip().lower()


def _day1_curated_aliases() -> list[tuple[Any, ...]]:
    """Verified Day 1 entity aliases strictly from Day1_Mon_16Nov artifacts."""
    rows = [
        # Finance initials seen in GL_Export & Payroll_Register
        ("FS", "VX014", "person", "Fatima Sheikh", "Entered By / Processed By initials in GL & Jan/Mar Payroll", DAY1_RELEASE_DATE),
        ("KS", "VX010", "person", "Karthik Subramanian", "Processed By initials in Feb-2026 Payroll Register", DAY1_RELEASE_DATE),
        # Transcript T1 & T2 person mishearings / nicknames
        ("Pria", "VX007", "person", "Priya Nair", "ASR mishearing in T1_CEO_Kickoff_Call.docx (P7)", DAY1_RELEASE_DATE),
        ("the new boy Rahul", "VX018", "person", "Rahul Verma", "Reference in T1_CEO_Kickoff_Call.docx (P7); joined 2026-02-03", DAY1_RELEASE_DATE),
        ("Vicky", "VX004", "person", "Vikram Menon", "Nickname in T2_CFO_Call.docx (P13)", DAY1_RELEASE_DATE),
        ("Kartik", "VX010", "person", "Karthik Subramanian", "ASR mishearing in T2_CFO_Call.docx (P8)", DAY1_RELEASE_DATE),
        ("Fatima Shaikh", "VX014", "person", "Fatima Sheikh", "ASR spelling in T2_CFO_Call.docx (P8)", DAY1_RELEASE_DATE),
        ("Ananya R.", "VX001", "person", "Ananya Rao", "Speaker label in T1 & T2 transcripts", DAY1_RELEASE_DATE),
        ("Meera I.", "VX003", "person", "Meera Iyer", "Speaker label in T2_CFO_Call.docx", DAY1_RELEASE_DATE),
        # Transcript T1 & T2 tool mishearings
        ("Joho books", "TOOL_ZOHO_BOOKS", "tool", "Zoho Books", "ASR mishearing in T2_CFO_Call.docx (P6)", DAY1_RELEASE_DATE),
        ("Kayka", "TOOL_KEKA", "tool", "Keka", "ASR mishearing in T2_CFO_Call.docx (P7)", DAY1_RELEASE_DATE),
        ("Jeera", "TOOL_JIRA", "tool", "Jira", "ASR mishearing in T1_CEO_Kickoff_Call.docx (P6)", DAY1_RELEASE_DATE),
        ("Cult Amp", "TOOL_CULTURE_AMP", "tool", "Culture Amp", "ASR mishearing in T1_CEO_Kickoff_Call.docx (P9)", DAY1_RELEASE_DATE),
        ("slag", "TOOL_SLACK", "tool", "Slack", "ASR mishearing in T1_CEO_Kickoff_Call.docx (P15); no Slack export in data room", DAY1_RELEASE_DATE),
        ("hub sport", "TOOL_HUBSPOT", "tool", "HubSpot", "ASR mishearing in T1_CEO_Kickoff_Call.docx (P14); no HubSpot export in data room", DAY1_RELEASE_DATE),
        ("Git Hub", "TOOL_GITHUB", "tool", "GitHub", "Spacing variant in T1_CEO_Kickoff_Call.docx (P6)", DAY1_RELEASE_DATE),
        # Vendors in GL_Export_Apr-Sep_2026.xlsx
        ("Patil Infra Services", "EXT001", "contractor", "Patil Infra Services", "External on-call contractor vendor in GL JV-0902 (ENG-OPS)", DAY1_RELEASE_DATE),
        ("Sapphire Events Pvt Ltd", "VEND_SAPPHIRE_EVT", "vendor", "Sapphire Events Pvt Ltd", "Marketing Summit venue/AV vendor in GL JV-0846 (MKT-EVT)", DAY1_RELEASE_DATE),
        ("Saphire Event Mgmt", "VEND_SAPPHIRE_MGT", "vendor", "Saphire Event Mgmt", "Marketing Summit catering vendor in GL JV-0904 (MKT-EVT); note single-p spelling", DAY1_RELEASE_DATE),
        ("Sapphire Residency Hotel", "VEND_SAPPHIRE_RES", "vendor", "Sapphire Residency Hotel", "Sales offsite hotel in GL JV-0918 (SAL-TRV) — distinct from MKT-EVT", DAY1_RELEASE_DATE),
        ("Cohere Recruiting Partners", "VEND_COHERE", "vendor", "Cohere Recruiting Partners", "Search firm paid 50% advance for 2 backend roles in GL JV-0688 (PPL-HIR)", DAY1_RELEASE_DATE),
        # Project aliases
        ("routing engine version three", "PROJ_ATLAS_V3", "project", "Atlas (routing engine v3)", "Referenced in T1_CEO_Kickoff_Call.docx (P4) & Board Updates", DAY1_RELEASE_DATE),
    ]
    return rows


def _day1_curated_evidence() -> list[tuple[Any, ...]]:
    """Verified atomic Day 1 evidence items strictly from Day1_Mon_16Nov."""
    return [
        ("E001", "Employee_Master.xlsx", "export", "Employees!row4-22", "Keka HRMS export (31-Oct-2026) lists 19 employees (VX001-VX019); contractors are excluded from Keka.", json.dumps(["VX001..VX019"]), "2026-10-31", DAY1_RELEASE_DATE, "High", None),
        ("E002", "Candidate_Brief.docx", "document", "P3", "Brief describes Veloxa Technologies as 'a 180-person B2B SaaS company in Bengaluru'.", json.dumps(["VX001"]), "", DAY1_RELEASE_DATE, "Low", "CG_HEADCOUNT"),
        ("E003", "T1_CEO_Kickoff_Call.docx", "transcript", "P4", "Ananya states company is 'roughly eighteen people (\"one-eighty, give or take\")', ARR 'around forty-two crore, maybe forty-five now', and burn 'around two point two' (unit unstated).", json.dumps(["VX001"]), "", DAY1_RELEASE_DATE, "Low", "CG_SIZE_ARR"),
        ("E004", "Board_Update_Apr-Jun_2026.pdf", "document", "page_1", "Q1 Board Update (sent 8 Jul 2026) reports ARR Rs. 5.8 Cr, 61 customers, Team 19, Monthly burn Rs. 46 L, Runway 14 months.", json.dumps(["VX001"]), "2026-07-08", DAY1_RELEASE_DATE, "High", "CG_SIZE_ARR"),
        ("E005", "Board_Update_Jul-Sep_2026.pdf", "document", "page_1", "Q2 Board Update (sent 6 Oct 2026) reports ARR Rs. 6.1 Cr, 66 customers, Team 19, Monthly burn Rs. 44 L, Runway 13 months.", json.dumps(["VX001"]), "2026-10-06", DAY1_RELEASE_DATE, "High", "CG_SIZE_ARR"),
        ("E006", "Board_Update_Apr-Jun_2026.pdf", "document", "page_1", "Q1 Board Update states Atlas (routing engine v3) is on track for GA on 15 September and two backend engineers will be added this quarter to de-risk Atlas.", json.dumps(["PROJ_ATLAS_V3"]), "2026-07-08", DAY1_RELEASE_DATE, "High", "CG_ATLAS_GA"),
        ("E007", "Board_Update_Jul-Sep_2026.pdf", "document", "page_1", "Q2 Board Update states Atlas is in 'final hardening', GA moved after a difficult August (no specific new date), hiring is paused while closing the round, and there is one planned departure in marketing.", json.dumps(["PROJ_ATLAS_V3", "VX013"]), "2026-10-06", DAY1_RELEASE_DATE, "High", "CG_ATLAS_GA"),
        ("E008", "T1_CEO_Kickoff_Call.docx", "transcript", "P4", "Ananya says routing engine v3 was promised to some customers 'by the festive season' and is not sure it will make it.", json.dumps(["VX001", "PROJ_ATLAS_V3"]), "", DAY1_RELEASE_DATE, "Low", "CG_ATLAS_GA"),
        ("E009", "T2_CFO_Call.docx", "transcript", "P4", "Meera says FY runs April to March ('FY twenty-six', note speaker may have said twenty-seven), starting ARR was 'forty-eight', burn 'two point two lakhs a month, sometimes two point five', and plans a hiring freeze if the raise slips.", json.dumps(["VX003"]), "", DAY1_RELEASE_DATE, "Low", "CG_SIZE_ARR"),
        ("E010", "T2_CFO_Call.docx", "transcript", "P7", "CFO confidentiality rule: Individual salaries 'must never show up in anything Ananya sees, only totals.'", json.dumps(["VX003", "VX001"]), "", DAY1_RELEASE_DATE, "High", None),
        ("E011", "T2_CFO_Call.docx", "transcript", "P6,P8,P9", "Meera notes books moved from Tally to Zoho Books ('Joho books') in Jan/Feb, Fatima was out for her wedding, and 'Nikhil's numbers never match mine' on marketing spend.", json.dumps(["VX003", "VX014", "VX006"]), "", DAY1_RELEASE_DATE, "Medium", None),
        ("E012", "Employee_Master.xlsx", "export", "Employees!row21", "Rahul Verma (VX018, Backend Engineer) joined on 2026-02-03 reporting to Vikram Menon (VX004).", json.dumps(["VX018", "VX004"]), "2026-02-03", DAY1_RELEASE_DATE, "High", "CG_FEB_PAYROLL"),
        ("E013", "Payroll_Register_Jan-Mar_2026.xlsx", "export", "Payroll Q4!row39,58", "In Feb-2026 (processed by KS), VX018 was paid for 28/28 days instead of 26/28 eligible days; Mar-2026 (processed by FS) shows no proration adjustment.", json.dumps(["VX018", "VX010", "VX014"]), "2026-02-28", DAY1_RELEASE_DATE, "High", "CG_FEB_PAYROLL"),
        ("E014", "01.eml", "email", "01.eml", "Karthik (VX010) emailed Meera (VX003) on 2026-02-28: 'Ran Feb payroll since Fatima is out. Used the Jan sheet and added the new joiner.'", json.dumps(["VX010", "VX003", "VX014"]), "2026-02-28", DAY1_RELEASE_DATE, "High", "CG_FEB_PAYROLL"),
        ("E015", "02.eml", "email", "02.eml & 03.eml", "Rahul (VX018) emailed Fatima (VX014) on 2026-03-06 noting his first payslip looked higher than expected for a partial month; Fatima replied on 2026-03-10 'Will check and get back.'", json.dumps(["VX018", "VX014"]), "2026-03-06", DAY1_RELEASE_DATE, "High", "CG_FEB_PAYROLL"),
        ("E016", "GL_Export_Apr-Sep_2026.xlsx", "export", "GL Apr-Sep!rows5,9,13,18,22,30", "Monthly GL PAYROLL total is Rs. 31,75,000/month from Apr to Sep 2026, matching Feb & Mar 2026 payroll register gross total.", json.dumps(["VX014"]), "2026-09-28", DAY1_RELEASE_DATE, "High", None),
        ("E017", "GL_Export_Apr-Sep_2026.xlsx", "export", "GL Apr-Sep!row15", "Voucher JV-0688 (2026-06-30): Paid Rs. 1,77,000 (PPL-HIR) to Cohere Recruiting Partners for 'Search fee, 2 backend roles (50% advance)'.", json.dumps(["VEND_COHERE"]), "2026-06-30", DAY1_RELEASE_DATE, "High", None),
        ("E018", "GL_Export_Apr-Sep_2026.xlsx", "export", "GL Apr-Sep!rows7,11,16,20,23,26,27", "Apr-Sep 2026 Marketing GL totals Rs. 14,26,620: MKT-PS Google Ads Rs. 4,23,620 + MKT-EVT Summit Rs. 10,03,000 (Sapphire Events Pvt Ltd Rs. 5,42,800 + Saphire Event Mgmt Rs. 4,60,200).", json.dumps(["VEND_SAPPHIRE_EVT", "VEND_SAPPHIRE_MGT"]), "2026-09-04", DAY1_RELEASE_DATE, "High", None),
        ("E019", "GL_Export_Apr-Sep_2026.xlsx", "export", "GL Apr-Sep!row29", "Voucher JV-0918 (2026-09-11): Sapphire Residency Hotel Rs. 38,940 is coded to SAL-TRV ('Sales offsite'), not Marketing.", json.dumps(["VEND_SAPPHIRE_RES"]), "2026-09-11", DAY1_RELEASE_DATE, "High", None),
        ("E020", "GL_Export_Apr-Sep_2026.xlsx", "export", "GL Apr-Sep!row25", "Voucher JV-0902 (2026-09-02): Patil Infra Services (PIS-108) paid Rs. 70,800 (ENG-OPS) for 'On-call support, 18-31 Aug'.", json.dumps(["EXT001"]), "2026-09-02", DAY1_RELEASE_DATE, "High", None),
        ("E021", "Employee_Master.xlsx", "export", "Employees!row16", "Siddharth Mehta (VX013, Product Marketing Manager) has status 'Notice period' with Exit Date 2026-10-31.", json.dumps(["VX013", "VX006"]), "2026-10-31", DAY1_RELEASE_DATE, "High", None),
    ]


def _day1_curated_conflicts() -> list[tuple[Any, ...]]:
    """Verified Day 1 cross-source conflicts strictly from Day1_Mon_16Nov."""
    return [
        (
            "C01",
            "Headcount (19 vs 180 / 18)",
            "E002",
            "E001",
            "Candidate_Brief.docx calls Veloxa '180-person' and T1 says 'eighteen people (\"one-eighty\")', whereas Employee_Master.xlsx has 19 rows and both Board Updates report Team = 19.",
            "resolved",
            "Active headcount is 19 employees (VX001-VX019); '180' and 'eighteen' are brief/ASR errors.",
            DAY1_RELEASE_DATE,
        ),
        (
            "C02",
            "ARR & Monthly Burn Scale",
            "E003",
            "E005",
            "T1 cites ARR '42-45 Cr' and burn '2.2', and T2 cites ARR '48' and burn '2.2-2.5 L/mo', whereas Q1/Q2 Board Updates report ARR Rs. 5.8 Cr -> 6.1 Cr and burn Rs. 46 L -> 44 L/mo (corroborated by Rs. 31.75 L monthly GL payroll).",
            "resolved",
            "Trust signed Q1/Q2 Board Updates and Zoho Books GL (ARR Rs. 5.8-6.1 Cr; burn Rs. 44-46 L/mo); T1/T2 figures are ASR/verbal errors.",
            DAY1_RELEASE_DATE,
        ),
        (
            "C03",
            "Feb 2026 Payroll Proration for VX018",
            "E012",
            "E013",
            "VX018 (Rahul Verma) joined 2026-02-03 (26/28 eligible days), yet Feb-2026 payroll (run by KS from Jan sheet) paid 28/28 days and Mar-2026 made no adjustment despite Rahul's query (02.eml) and Fatima's reply (03.eml).",
            "open",
            "Confirmed unresolved February payroll overpayment bug; flag as an open Finance control item without disclosing individual salary amounts.",
            DAY1_RELEASE_DATE,
        ),
        (
            "C04",
            "Atlas v3 Launch Timing",
            "E006",
            "E007",
            "Q1 Board Update targeted Atlas v3 GA for 2026-09-15; Q2 Board Update (sent Oct 6) says GA moved for 'final hardening' with no new date, while T1 expresses doubt on making the festive season.",
            "open",
            "As of Day 1 (2026-11-16), Sep 15 GA was missed and no revised target date is present in Day 1 files.",
            DAY1_RELEASE_DATE,
        ),
        (
            "C05",
            "Fiscal Year Label in T2",
            "E009",
            "E004",
            "T2_CFO_Call.docx transcribes 'FY twenty-six (note: speaker may have said twenty-seven)' for the April-March year covering 2026.",
            "resolved",
            "Apr 2026 - Mar 2027 is FY27 (India FY convention); 'FY twenty-six' is a recognized ASR mishearing.",
            DAY1_RELEASE_DATE,
        ),
    ]


def _sync_postgres(
    db: DatabaseManager,
    employees_rows: list[tuple[Any, ...]],
    reporting_rows: list[tuple[Any, ...]],
    gl_rows: list[tuple[Any, ...]],
    payroll_sum_rows: list[tuple[Any, ...]],
    payroll_res_rows: list[tuple[Any, ...]],
    alias_rows: list[tuple[Any, ...]],
    evidence_rows: list[tuple[Any, ...]],
    conflict_rows: list[tuple[Any, ...]],
    email_rows: list[tuple[Any, ...]],
    doc_rows: list[tuple[Any, ...]],
    root: Path,
    files_loaded: int,
    records_loaded: int,
) -> None:
    """Upsert Day 1 records into Supabase PostgreSQL."""
    with db.postgres_conn() as pg_conn:
        with pg_conn.cursor() as cur:
            if employees_rows:
                pg_emps = [(*r[:11], bool(r[11]), r[12]) for r in employees_rows]
                cur.executemany(
                    """INSERT INTO employees
                    (entity_id, full_name, email, department, title, manager_id, join_date,
                     exit_date, location, employment_type, status, is_agent_persona, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (entity_id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        department = EXCLUDED.department,
                        title = EXCLUDED.title,
                        manager_id = EXCLUDED.manager_id,
                        join_date = EXCLUDED.join_date,
                        exit_date = EXCLUDED.exit_date,
                        location = EXCLUDED.location,
                        employment_type = EXCLUDED.employment_type,
                        status = EXCLUDED.status,
                        is_agent_persona = EXCLUDED.is_agent_persona,
                        release_date = EXCLUDED.release_date""",
                    pg_emps,
                )
            if reporting_rows:
                cur.execute(
                    "DELETE FROM reporting_lines WHERE release_date = %s AND source_ref = %s",
                    (DAY1_RELEASE_DATE, "Employee_Master.xlsx"),
                )
                cur.executemany(
                    """INSERT INTO reporting_lines
                    (employee_id, manager_id, department, effective_from, effective_to, source_ref, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    reporting_rows,
                )
            if gl_rows:
                cur.executemany(
                    """INSERT INTO gl_transactions
                    (voucher_id, txn_date, event_date, account_code, account_name, cost_center,
                     vendor_name, canonical_vendor, description, amount_inr, entered_by,
                     source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (voucher_id) DO UPDATE SET
                        txn_date = EXCLUDED.txn_date,
                        event_date = EXCLUDED.event_date,
                        account_code = EXCLUDED.account_code,
                        account_name = EXCLUDED.account_name,
                        cost_center = EXCLUDED.cost_center,
                        vendor_name = EXCLUDED.vendor_name,
                        canonical_vendor = EXCLUDED.canonical_vendor,
                        description = EXCLUDED.description,
                        amount_inr = EXCLUDED.amount_inr,
                        entered_by = EXCLUDED.entered_by,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    gl_rows,
                )
            if payroll_sum_rows:
                cur.executemany(
                    """INSERT INTO payroll_summary
                    (period_month, department, headcount, total_gross_inr, total_net_inr,
                     prepared_by, notes, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (period_month, department, source_file) DO UPDATE SET
                        headcount = EXCLUDED.headcount,
                        total_gross_inr = EXCLUDED.total_gross_inr,
                        total_net_inr = EXCLUDED.total_net_inr,
                        prepared_by = EXCLUDED.prepared_by,
                        notes = EXCLUDED.notes,
                        release_date = EXCLUDED.release_date""",
                    payroll_sum_rows,
                )
            if payroll_res_rows:
                cur.executemany(
                    """INSERT INTO payroll_restricted
                    (period_month, employee_id, days_paid, days_in_month, gross_inr, net_inr,
                     prepared_by, anomaly_flag, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (period_month, employee_id, source_file) DO UPDATE SET
                        days_paid = EXCLUDED.days_paid,
                        days_in_month = EXCLUDED.days_in_month,
                        gross_inr = EXCLUDED.gross_inr,
                        net_inr = EXCLUDED.net_inr,
                        prepared_by = EXCLUDED.prepared_by,
                        anomaly_flag = EXCLUDED.anomaly_flag,
                        release_date = EXCLUDED.release_date""",
                    payroll_res_rows,
                )
            if alias_rows:
                cur.executemany(
                    """INSERT INTO entity_aliases
                    (alias_text, canonical_id, entity_type, canonical_name, notes, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (alias_text, canonical_id) DO UPDATE SET
                        entity_type = EXCLUDED.entity_type,
                        canonical_name = EXCLUDED.canonical_name,
                        notes = EXCLUDED.notes,
                        release_date = EXCLUDED.release_date""",
                    alias_rows,
                )
            if evidence_rows:
                cur.executemany(
                    """INSERT INTO evidence_index
                    (evidence_id, source_file, source_type, location, fact_text, entities_json,
                     event_date, release_date, reliability, conflict_group_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (evidence_id) DO UPDATE SET
                        source_file = EXCLUDED.source_file,
                        source_type = EXCLUDED.source_type,
                        location = EXCLUDED.location,
                        fact_text = EXCLUDED.fact_text,
                        entities_json = EXCLUDED.entities_json,
                        event_date = EXCLUDED.event_date,
                        release_date = EXCLUDED.release_date,
                        reliability = EXCLUDED.reliability,
                        conflict_group_id = EXCLUDED.conflict_group_id""",
                    evidence_rows,
                )
            if conflict_rows:
                cur.executemany(
                    """INSERT INTO conflicts
                    (conflict_id, topic, claim_a_evidence_id, claim_b_evidence_id, summary,
                     resolution_status, verified_conclusion, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (conflict_id) DO UPDATE SET
                        topic = EXCLUDED.topic,
                        claim_a_evidence_id = EXCLUDED.claim_a_evidence_id,
                        claim_b_evidence_id = EXCLUDED.claim_b_evidence_id,
                        summary = EXCLUDED.summary,
                        resolution_status = EXCLUDED.resolution_status,
                        verified_conclusion = EXCLUDED.verified_conclusion,
                        release_date = EXCLUDED.release_date""",
                    conflict_rows,
                )
            if email_rows:
                cur.executemany(
                    """INSERT INTO emails
                    (email_id, sender_raw, sender_entity_id, recipients_raw, cc_raw, subject,
                     sent_at, event_date, body_text, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email_id) DO UPDATE SET
                        sender_raw = EXCLUDED.sender_raw,
                        sender_entity_id = EXCLUDED.sender_entity_id,
                        recipients_raw = EXCLUDED.recipients_raw,
                        cc_raw = EXCLUDED.cc_raw,
                        subject = EXCLUDED.subject,
                        sent_at = EXCLUDED.sent_at,
                        event_date = EXCLUDED.event_date,
                        body_text = EXCLUDED.body_text,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    email_rows,
                )
            if doc_rows:
                cur.executemany(
                    """INSERT INTO documents
                    (doc_id, source_file, doc_type, title, section_label, content_text,
                     event_date, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        source_file = EXCLUDED.source_file,
                        doc_type = EXCLUDED.doc_type,
                        title = EXCLUDED.title,
                        section_label = EXCLUDED.section_label,
                        content_text = EXCLUDED.content_text,
                        event_date = EXCLUDED.event_date,
                        release_date = EXCLUDED.release_date""",
                    doc_rows,
                )
            cur.execute(
                """INSERT INTO ingestion_runs
                (release_tag, release_date, source_dir, files_loaded, records_loaded, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (release_tag) DO UPDATE SET
                    release_date = EXCLUDED.release_date,
                    source_dir = EXCLUDED.source_dir,
                    files_loaded = EXCLUDED.files_loaded,
                    records_loaded = EXCLUDED.records_loaded,
                    status = EXCLUDED.status,
                    loaded_at = CURRENT_TIMESTAMP""",
                (DAY1_TAG, DAY1_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
            )


def ingest_day1(data_dir: str | Path, db: DatabaseManager | None = None) -> dict[str, Any]:
    """Ingest Day 1 files from `data_dir` into SQLite and (if set) Supabase Postgres."""
    db = db or DatabaseManager()
    db.init_schema(sync_postgres=True)

    root = _find_day1_root(Path(data_dir).expanduser().resolve())
    if not root.exists():
        raise FileNotFoundError(f"Day 1 data directory not found: {root}")

    files_loaded = 0

    import pandas as pd

    employees_rows: list[tuple[Any, ...]] = []
    reporting_rows: list[tuple[Any, ...]] = []
    gl_rows: list[tuple[Any, ...]] = []
    payroll_sum_rows: list[tuple[Any, ...]] = []
    payroll_res_rows: list[tuple[Any, ...]] = []
    alias_rows: list[tuple[Any, ...]] = []
    evidence_rows: list[tuple[Any, ...]] = []
    conflict_rows: list[tuple[Any, ...]] = []
    email_rows: list[tuple[Any, ...]] = []
    doc_rows: list[tuple[Any, ...]] = []

    emp_dept_map: dict[str, str] = {}
    emp_join_map: dict[str, str] = {}
    emp_email_map: dict[str, str] = {}

    xlsx_files = _iter_files(root, (".xlsx",))
    # Parse Employee_Master.xlsx first so Payroll & Email parsers can resolve department/join_date/email
    xlsx_files.sort(key=lambda p: (0 if "employee_master" in p.name.lower() else 1, p.name))

    # 1. Spreadsheets (.xlsx)
    for xlsx_path in xlsx_files:
        fname = xlsx_path.name
        xl = pd.ExcelFile(xlsx_path)
        files_loaded += 1

        if "employee_master" in fname.lower():
            records = _read_xlsx_sheet(
                xlsx_path,
                xl.sheet_names[0],
                {"emp_id", "employee_id", "full_name"},
            )
            for r in records:
                emp_id = str(_pick(r, "emp_id", "employee_id", "id", "entity_id")).strip()
                if not emp_id:
                    continue
                dept = str(_pick(r, "department", "dept")).strip()
                work_email = str(_pick(r, "work_email", "email")).strip()
                manager_id = str(_pick(r, "manager_id", "reports_to", "manager")).strip()
                join_date = _to_iso_date(_pick(r, "join_date", "joining_date", "start_date"))
                exit_date = _to_iso_date(_pick(r, "exit_date", "last_working_day"))
                status = str(_pick(r, "status", default="Active")).strip()
                emp_type = str(_pick(r, "employment_type", "type", default="FTE")).strip()
                is_agent = int(dept in AGENT_DEPARTMENTS and emp_id.startswith("VX") and emp_id != "VX001")

                emp_dept_map[emp_id] = dept
                if join_date:
                    emp_join_map[emp_id] = join_date
                if work_email:
                    emp_email_map[work_email.lower()] = emp_id

                employees_rows.append((
                    emp_id,
                    str(_pick(r, "full_name", "name", "employee_name")).strip(),
                    work_email,
                    dept,
                    str(_pick(r, "title", "role", "designation")).strip(),
                    manager_id,
                    join_date,
                    exit_date,
                    str(_pick(r, "location", "city")).strip(),
                    emp_type,
                    status,
                    is_agent,
                    DAY1_RELEASE_DATE,
                ))
                reporting_rows.append((
                    emp_id,
                    manager_id or None,
                    dept,
                    join_date or "2019-04-01",
                    exit_date or None,
                    fname,
                    DAY1_RELEASE_DATE,
                ))

        elif "gl_export" in fname.lower():
            records = _read_xlsx_sheet(
                xlsx_path,
                xl.sheet_names[0],
                {"txn_date", "voucher", "voucher_id", "cost_centre"},
            )
            for idx, r in enumerate(records, start=1):
                voucher = str(_pick(r, "voucher", "voucher_id", "jv_no", "journal_id", "id", default=f"GL-{idx:04d}")).strip()
                if not voucher:
                    continue
                txn_date = _to_iso_date(_pick(r, "txn_date", "date", "posting_date"))
                cost_centre = str(_pick(r, "cost_centre", "cost_center", "department", "cc")).strip()
                ref_code = str(_pick(r, "ref", "account_code", "gl_code", "account", default=cost_centre)).strip()
                amount_raw = _pick(r, "amount_(rs.)", "amount_inr", "amount", "debit", "net_amount", default=0)
                try:
                    amount = float(str(amount_raw).replace(",", "").strip() or 0)
                except ValueError:
                    amount = 0.0
                vendor = str(_pick(r, "vendor_/_payee", "vendor_name", "vendor", "party")).strip()
                gl_rows.append((
                    voucher,
                    txn_date,
                    txn_date[:10] if txn_date else "",
                    ref_code or cost_centre or "GL",
                    str(_pick(r, "account_name", "category", default=cost_centre)).strip(),
                    cost_centre,
                    vendor,
                    vendor,
                    str(_pick(r, "narration", "description", "memo")).strip(),
                    amount,
                    str(_pick(r, "entered_by", "created_by", "preparer")).strip(),
                    fname,
                    DAY1_RELEASE_DATE,
                ))

        elif "payroll_register" in fname.lower():
            for sheet in xl.sheet_names:
                records = _read_xlsx_sheet(
                    xlsx_path,
                    sheet,
                    {"emp_id", "employee_id", "gross_(rs.)", "gross_inr"},
                )
                dept_totals: dict[str, dict[str, Any]] = {}
                for r in records:
                    emp_id = str(_pick(r, "emp_id", "employee_id", "id")).strip()
                    if not emp_id:
                        continue
                    raw_period = _pick(r, "month", "period_month", "period", default=sheet)
                    period = _normalize_month(raw_period)
                    dept = str(_pick(r, "department", "dept", default=emp_dept_map.get(emp_id, "All"))).strip()
                    gross = float(str(_pick(r, "gross_(rs.)", "gross_inr", "gross_salary", "gross", default=0)).replace(",", "") or 0)
                    net = float(str(_pick(r, "net_(rs.)", "net_inr", "net_salary", "net_pay", default=0)).replace(",", "") or 0)
                    days_paid_raw = _pick(r, "days_payable", "days_paid", "paid_days", default=None)
                    days_month_raw = _pick(r, "days_in_month", "total_days", default=None)
                    days_paid = float(days_paid_raw) if days_paid_raw not in ("", None) else None
                    days_month = int(float(days_month_raw)) if days_month_raw not in ("", None) else None
                    preparer = str(_pick(r, "processed_by", "prepared_by", "run_by")).strip()
                    anomaly_flag = str(_pick(r, "anomaly_flag", "notes", default="")).strip()

                    join_dt = emp_join_map.get(emp_id, "")
                    if not anomaly_flag and join_dt and join_dt[:7] == period and days_paid and days_month:
                        join_day = int(join_dt[8:10])
                        eligible_days = days_month - (join_day - 1)
                        if days_paid > eligible_days:
                            anomaly_flag = (
                                f"PRORATION_OVERPAYMENT: joined {join_dt} "
                                f"({eligible_days}/{days_month} eligible) but paid {int(days_paid)}/{days_month} days"
                            )

                    payroll_res_rows.append((
                        period,
                        emp_id,
                        days_paid,
                        days_month,
                        gross,
                        net,
                        preparer,
                        anomaly_flag,
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
            records = _read_xlsx_sheet(
                xlsx_path,
                xl.sheet_names[0],
                {"name_or_identifier_as_seen", "alias_text", "resolves_to", "canonical_id"},
            )
            for r in records:
                alias_txt = str(_pick(r, "name_or_identifier_as_seen", "alias_text", "alias", "raw_name")).strip()
                canon_id = str(_pick(r, "resolves_to", "canonical_id", "entity_id", "id")).strip()
                if alias_txt and canon_id:
                    alias_rows.append((
                        alias_txt,
                        canon_id,
                        str(_pick(r, "kind_(person/vendor/project)", "entity_type", "type", default="person")).strip(),
                        canon_id,
                        str(_pick(r, "seen_in_(file)", "notes", default="")).strip(),
                        DAY1_RELEASE_DATE,
                    ))

        elif "evidence_index" in fname.lower():
            records = _read_xlsx_sheet(
                xlsx_path,
                xl.sheet_names[0],
                {"ref", "evidence_id", "fact_(your_words)", "fact_text"},
            )
            for idx, r in enumerate(records, start=1):
                ev_id = str(_pick(r, "ref", "evidence_id", "id", default=f"E-TMPL-{idx:03d}")).strip()
                fact = str(_pick(r, "fact_(your_words)", "fact_text", "fact", "claim", "summary")).strip()
                if not fact:
                    continue
                evidence_rows.append((
                    ev_id,
                    str(_pick(r, "file", "source_file", "source", default=fname)).strip(),
                    str(_pick(r, "source_type", "type", default="export")).strip(),
                    str(_pick(r, "sheet_/_page_/_row", "location", "ref", default="sheet1")).strip(),
                    fact,
                    json.dumps([str(_pick(r, "entities_named", "entities", default=""))]),
                    _to_iso_date(_pick(r, "date_(normalised,_ist)", "event_date", default="")),
                    DAY1_RELEASE_DATE,
                    str(_pick(r, "confidence_(h/m/l)", "reliability", default="Medium")).strip(),
                    str(_pick(r, "conflict_group_id", default="")).strip() or None,
                ))

    # 2. Emails (.eml)
    for eml_path in _iter_files(root, (".eml",)):
        files_loaded += 1
        parsed = _parse_eml(eml_path)
        sender_email = _extract_email_addr(parsed["sender_raw"])
        sender_id = emp_email_map.get(sender_email)
        email_rows.append((
            parsed["email_id"],
            parsed["sender_raw"],
            sender_id,
            parsed["recipients_raw"],
            parsed["cc_raw"],
            parsed["subject"],
            parsed["sent_at"],
            _parse_email_iso_date(parsed["sent_at"]),
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
    pdf_event_dates = {
        "Board_Update_Apr-Jun_2026.pdf": "2026-07-08",
        "Board_Update_Jul-Sep_2026.pdf": "2026-10-06",
    }
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
                pdf_event_dates.get(pdf_path.name, ""),
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
            "2026-10-31" if txt_path.name == "README.txt" else "",
            DAY1_RELEASE_DATE,
        ))

    # 6. Seed verified Day 1 entity_aliases, evidence_index, and conflicts when full Day 1 pack is present
    is_full_day1_pack = len(employees_rows) >= 19 and any(d[1].startswith("T1_") for d in doc_rows)
    if is_full_day1_pack:
        alias_rows.extend(_day1_curated_aliases())
        if not evidence_rows:
            evidence_rows.extend(_day1_curated_evidence())
        conflict_rows.extend(_day1_curated_conflicts())

    records_loaded = (
        len(employees_rows)
        + len(reporting_rows)
        + len(gl_rows)
        + len(payroll_sum_rows)
        + len(payroll_res_rows)
        + len(alias_rows)
        + len(evidence_rows)
        + len(conflict_rows)
        + len(email_rows)
        + len(doc_rows)
    )

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
        if reporting_rows:
            conn.execute(
                "DELETE FROM reporting_lines WHERE release_date = ? AND source_ref = ?",
                (DAY1_RELEASE_DATE, "Employee_Master.xlsx"),
            )
            conn.executemany(
                """INSERT INTO reporting_lines
                (employee_id, manager_id, department, effective_from, effective_to, source_ref, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                reporting_rows,
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
                """INSERT OR REPLACE INTO entity_aliases
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
        if conflict_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO conflicts
                (conflict_id, topic, claim_a_evidence_id, claim_b_evidence_id, summary,
                 resolution_status, verified_conclusion, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                conflict_rows,
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

        conn.execute(
            """INSERT OR REPLACE INTO ingestion_runs
            (release_tag, release_date, source_dir, files_loaded, records_loaded, status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (DAY1_TAG, DAY1_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
        )

    pg_synced = False
    if db.postgres_enabled:
        _sync_postgres(
            db=db,
            employees_rows=employees_rows,
            reporting_rows=reporting_rows,
            gl_rows=gl_rows,
            payroll_sum_rows=payroll_sum_rows,
            payroll_res_rows=payroll_res_rows,
            alias_rows=alias_rows,
            evidence_rows=evidence_rows,
            conflict_rows=conflict_rows,
            email_rows=email_rows,
            doc_rows=doc_rows,
            root=root,
            files_loaded=files_loaded,
            records_loaded=records_loaded,
        )
        pg_synced = True

    return {
        "release_tag": DAY1_TAG,
        "release_date": DAY1_RELEASE_DATE,
        "files_loaded": files_loaded,
        "records_loaded": records_loaded,
        "counts": {
            "employees": len(employees_rows),
            "reporting_lines": len(reporting_rows),
            "gl_transactions": len(gl_rows),
            "payroll_summary": len(payroll_sum_rows),
            "payroll_restricted": len(payroll_res_rows),
            "entity_aliases": len(alias_rows),
            "evidence_index": len(evidence_rows),
            "conflicts": len(conflict_rows),
            "emails": len(email_rows),
            "documents": len(doc_rows),
        },
        "postgres_synced": pg_synced,
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
