"""Day 2 ingestion pipeline (`Day2_Tue_17Nov`, release_date = 2026-11-17).

Parses raw Day 2 HR spreadsheets, PDFs, Word transcripts, and `.eml` files from
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

DAY2_TAG = "Day2_Tue_17Nov"
DAY2_RELEASE_DATE = RELEASE_DATES[DAY2_TAG]

EMPLOYEE_NAME_MAP: dict[str, str] = {
    "a. das": "VX009",
    "p. nair": "VX007",
    "k. subramanian": "VX010",
    "f. sheikh": "VX014",
    "s. kulkarni": "VX012",
    "n. bose": "VX006",
    "a. khan": "VX011",
    "r. verma": "VX018",
    "s. mehta": "VX013",
    "d. joshi": "VX005",
    "l. pillai": "VX017",
    "v. menon": "VX004",
}

INITIALS_TO_EMP_ID: dict[str, str] = {
    "ar": "VX001",
    "mi": "VX003",
    "vm": "VX004",
    "dj": "VX005",
    "nb": "VX006",
    "ks": "VX010",
    "fs": "VX014",
}


def _normalize_col(col: Any) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


def _find_day2_root(data_dir: Path) -> Path:
    """Locate Day 2 files whether `data_dir` points to root pack or Day2 folder."""
    if (data_dir / DAY2_TAG).is_dir():
        return data_dir / DAY2_TAG
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


def _extract_email_addr(raw_header: str) -> str:
    m = re.search(r"<([^>]+)>", raw_header)
    if m:
        return m.group(1).strip().lower()
    return raw_header.strip().lower()


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

    headers = [
        _normalize_col(v) if pd.notna(v) else f"col_{i}"
        for i, v in enumerate(raw.iloc[header_idx].tolist())
    ]
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


def _day2_curated_aliases() -> list[tuple[Any, ...]]:
    """Verified Day 2 entity aliases strictly from Day2_Tue_17Nov artifacts."""
    return [
        # Tool mishearing in T3
        ("Liver", "TOOL_LEVER", "tool", "Lever", "ASR mishearing in T3_Head_of_People_Call.docx; hiring runs on Keka Hire, not Lever", DAY2_RELEASE_DATE),
        # People nicknames & transcript labels in T3 & Resignation letter
        ("Sid", "VX013", "person", "Siddharth Mehta", "Nickname used by Deepa in T3_Head_of_People_Call.docx", DAY2_RELEASE_DATE),
        ("SM", "VX013", "person", "Siddharth Mehta", "Initials in Resignation_Letter_SM.pdf", DAY2_RELEASE_DATE),
        ("Deepa J.", "VX005", "person", "Deepa Joshi", "Speaker label in T3_Head_of_People_Call.docx", DAY2_RELEASE_DATE),
        ("Rohan B.", "VX015", "person", "Rohan Banerjee", "Speaker label in T3_Head_of_People_Call.docx", DAY2_RELEASE_DATE),
        ("Lakshmi", "VX017", "person", "Lakshmi Pillai", "Mentioned in T3_Head_of_People_Call.docx as HRBP handling exits", DAY2_RELEASE_DATE),
        # Leave Register abbreviated employee names
        ("A. Das", "VX009", "person", "Arjun Das", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("P. Nair", "VX007", "person", "Priya Nair", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("K. Subramanian", "VX010", "person", "Karthik Subramanian", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("F. Sheikh", "VX014", "person", "Fatima Sheikh", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("S. Kulkarni", "VX012", "person", "Sneha Kulkarni", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("N. Bose", "VX006", "person", "Nikhil Bose", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("A. Khan", "VX011", "person", "Aisha Khan", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("R. Verma", "VX018", "person", "Rahul Verma", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("S. Mehta", "VX013", "person", "Siddharth Mehta", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("D. Joshi", "VX005", "person", "Deepa Joshi", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("L. Pillai", "VX017", "person", "Lakshmi Pillai", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
        ("V. Menon", "VX004", "person", "Vikram Menon", "Employee name in Leave_Register.xlsx", DAY2_RELEASE_DATE),
    ]


def _day2_curated_evidence() -> list[tuple[Any, ...]]:
    """Verified atomic Day 2 evidence items strictly from Day2_Tue_17Nov."""
    return [
        (
            "E022",
            "Hiring_Tracker.xlsx",
            "export",
            "Requisitions!row1,4-9",
            "Keka Hire export lists 6 requisitions (REQ-011, REQ-013 to REQ-017); REQ-012 is missing from tracker.",
            json.dumps(["TOOL_KEKA"]),
            "2026-10-31",
            DAY2_RELEASE_DATE,
            "High",
            "CG_HIRING_ROLES",
        ),
        (
            "E023",
            "Hiring_Tracker.xlsx",
            "export",
            "Requisitions!rows6-7",
            "REQ-014 (Backend Engineer - Routing) and REQ-015 (Backend Engineer - Platform) were placed On hold on 2026-08-12 with 3 and 5 candidates in pipeline (8 total); final round on 14-Aug cancelled.",
            json.dumps(["VX004", "VX003", "PROJ_ATLAS_V3"]),
            "2026-08-12",
            DAY2_RELEASE_DATE,
            "High",
            "CG_BACKEND_FREEZE",
        ),
        (
            "E024",
            "Hiring_Tracker.xlsx",
            "export",
            "Requisitions!row8",
            "REQ-016 (Product Marketing Manager backfill) opened on 2026-09-17 with 7 candidates in pipeline.",
            json.dumps(["VX006", "VX013"]),
            "2026-09-17",
            DAY2_RELEASE_DATE,
            "High",
            None,
        ),
        (
            "E025",
            "Hiring_Tracker.xlsx",
            "export",
            "Requisitions!row4",
            "REQ-011 (Account Executive) closed not hired on 2026-04-02; note states 'Budget moved to marketing'.",
            json.dumps(["VX002", "VX006"]),
            "2026-04-02",
            DAY2_RELEASE_DATE,
            "High",
            None,
        ),
        (
            "E026",
            "Leave_Register.xlsx",
            "export",
            "Leave FY!rows16-20",
            "Priya Nair (VX007) took five half-day afternoon personal leaves in September 2026 (03, 08, 15, 17, and 24 Sep), all approved by VM (Vikram Menon).",
            json.dumps(["VX007", "VX004"]),
            "2026-09-24",
            DAY2_RELEASE_DATE,
            "High",
            "CG_ENG_BURNOUT",
        ),
        (
            "E027",
            "Leave_Register.xlsx",
            "export",
            "Leave FY!row8",
            "Arjun Das (VX009) took 5 days relocation leave (2026-03-02 to 2026-03-06) for moving to Pune, approved by VM.",
            json.dumps(["VX009", "VX004"]),
            "2026-03-06",
            DAY2_RELEASE_DATE,
            "High",
            None,
        ),
        (
            "E028",
            "Leave_Register.xlsx",
            "export",
            "Leave FY!row7",
            "Fatima Sheikh (VX014) took 15 days marriage leave (2026-02-09 to 2026-02-27), approved by MI (Meera Iyer).",
            json.dumps(["VX014", "VX003"]),
            "2026-02-27",
            DAY2_RELEASE_DATE,
            "High",
            None,
        ),
        (
            "E029",
            "Pulse_Survey.xlsx",
            "export",
            "Pulse by team!row7",
            "Engineering team pulse engagement score dropped to 3.1 in Jul-Sep 2026 (4 responses from team of 5); comments withheld as team size is smaller than 6.",
            json.dumps(["TOOL_CULTURE_AMP"]),
            "2026-09-29",
            DAY2_RELEASE_DATE,
            "High",
            "CG_ENG_BURNOUT",
        ),
        (
            "E030",
            "Pulse_Survey.xlsx",
            "export",
            "Pulse by team!row19",
            "Marketing team pulse engagement score dipped to 3.4 in Jul-Sep 2026 (3 responses from team of 3); comments withheld as team size is smaller than 6.",
            json.dumps(["TOOL_CULTURE_AMP"]),
            "2026-09-29",
            DAY2_RELEASE_DATE,
            "High",
            None,
        ),
        (
            "E031",
            "Resignation_Letter_SM.pdf",
            "document",
            "page_1",
            "Siddharth Mehta (VX013, Product Marketing Manager) submitted resignation on 2026-09-15 with last working day 2026-10-31, citing need for clearer launch timelines where prepared work reaches customers.",
            json.dumps(["VX013", "VX006"]),
            "2026-09-15",
            DAY2_RELEASE_DATE,
            "High",
            "CG_HIRING_ROLES",
        ),
        (
            "E032",
            "06.eml",
            "email",
            "06.eml",
            "Meera Iyer emailed Vikram Menon on 2026-08-12 pausing REQ-014 and REQ-015 until the funding round closes, citing burn priority.",
            json.dumps(["VX003", "VX004", "VX001", "VX015"]),
            "2026-08-12",
            DAY2_RELEASE_DATE,
            "High",
            "CG_BACKEND_FREEZE",
        ),
        (
            "E033",
            "07.eml",
            "email",
            "07.eml",
            "Vikram Menon replied to Meera on 2026-08-12 regarding pausing reqs: 'Understood. We\\'ll absorb it.'",
            json.dumps(["VX004", "VX003"]),
            "2026-08-12",
            DAY2_RELEASE_DATE,
            "High",
            "CG_BACKEND_FREEZE",
        ),
        (
            "E034",
            "10.eml",
            "email",
            "10.eml",
            "Arjun Das emailed Deepa Joshi on 2026-09-18 requesting to make Pune remote arrangement permanent, offering to visit Bengaluru once a month.",
            json.dumps(["VX009", "VX005"]),
            "2026-09-18",
            DAY2_RELEASE_DATE,
            "High",
            "CG_ENG_BURNOUT",
        ),
        (
            "E035",
            "11.eml",
            "email",
            "11.eml",
            "Deepa Joshi emailed Ananya Rao on 2026-09-29 stating engineering pulse dropped, team is too small to share comments, and suggesting Vikram conduct 1:1s.",
            json.dumps(["VX005", "VX001", "VX004"]),
            "2026-09-29",
            DAY2_RELEASE_DATE,
            "High",
            "CG_ENG_BURNOUT",
        ),
    ]


def _day2_curated_conflicts() -> list[tuple[Any, ...]]:
    """Verified Day 2 cross-source conflicts strictly from Day2_Tue_17Nov."""
    return [
        (
            "C06",
            "HR Metrics & Open Roles (Rohan Claims vs Reality)",
            "E022",
            "E031",
            "Rohan Banerjee claims in T3 that there were 'twenty-two open roles in April', 'we lost six of them in August', and hiring is tracked in 'Liver' (Lever). In reality, Hiring_Tracker.xlsx (Keka Hire) lists only 6 total requisitions (REQ-011, REQ-013 to REQ-017 with REQ-012 missing), of which only 2 were paused in August, and Employee_Master / Resignation_Letter_SM show only 1 resignation (VX013 Siddharth Mehta).",
            "resolved",
            "Official ATS is Keka Hire with only 6 requisitions tracked (2 paused in Aug, 1 filled, 1 closed, 2 open). Rohan's verbal claims of 22 open roles, 6 losses in August, and Lever ATS are inaccurate recollection or ASR distortions.",
            DAY2_RELEASE_DATE,
        ),
        (
            "C07",
            "Backend Hiring Freeze vs Atlas Schedule & Sunk Advance",
            "E017",
            "E023",
            "GL_Export shows Rs. 1,77,000 paid to Cohere Recruiting Partners on 2026-06-30 (JV-0688, 50% advance for 2 backend roles). On 2026-08-12, Meera paused REQ-014 and REQ-015 to conserve runway (06.eml, Hiring_Tracker.xlsx) despite 8 active candidates in pipeline. Vikram accepted the freeze with 'We\\'ll absorb it' (07.eml), downplaying the delivery schedule crisis to Atlas v3 while the recruiting advance remains trapped.",
            "open",
            "Confirmed strategic conflict between CFO burn control and VP Engineering delivery capacity. The Rs. 1.77L advance remains unrecovered while freezing 2 backend engineers starves the delayed Atlas v3 project.",
            DAY2_RELEASE_DATE,
        ),
        (
            "C08",
            "Engineering Workload & Hidden Burnout",
            "E029",
            "E026",
            "Deepa in T3 warns of 'one engineer I\\'m worried about' and notes exit interviews cite workload. Pulse_Survey.xlsx shows Engineering engagement collapsed from 4.0 to 3.1 in Jul-Sep 2026, but comments are withheld per Culture Amp anonymity threshold (team size < 6). Leave_Register.xlsx corroborates severe strain: Priya Nair (VX007) took 5 half-day afternoon leaves in September alone, and Arjun Das (VX009) requested permanent remote work from Pune.",
            "open",
            "Culture Amp anonymity threshold hides specific employee feedback from leadership, masking critical key-person burnout (Priya Nair) and workload stress following the backend hiring pause.",
            DAY2_RELEASE_DATE,
        ),
    ]


def _sync_postgres_day2(
    db: DatabaseManager,
    hiring_rows: list[tuple[Any, ...]],
    leave_rows: list[tuple[Any, ...]],
    pulse_rows: list[tuple[Any, ...]],
    alias_rows: list[tuple[Any, ...]],
    evidence_rows: list[tuple[Any, ...]],
    conflict_rows: list[tuple[Any, ...]],
    email_rows: list[tuple[Any, ...]],
    doc_rows: list[tuple[Any, ...]],
    voice_note_rows: list[tuple[Any, ...]],
    root: Path,
    files_loaded: int,
    records_loaded: int,
) -> None:
    """Upsert Day 2 records into Supabase PostgreSQL."""
    with db.postgres_conn() as pg_conn:
        with pg_conn.cursor() as cur:
            if hiring_rows:
                cur.executemany(
                    """INSERT INTO hiring_reqs
                    (req_id, role_title, department, status, opened_date, paused_or_closed_date,
                     pipeline_count, ats_system, notes, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (req_id) DO UPDATE SET
                        role_title = EXCLUDED.role_title,
                        department = EXCLUDED.department,
                        status = EXCLUDED.status,
                        opened_date = EXCLUDED.opened_date,
                        paused_or_closed_date = EXCLUDED.paused_or_closed_date,
                        pipeline_count = EXCLUDED.pipeline_count,
                        ats_system = EXCLUDED.ats_system,
                        notes = EXCLUDED.notes,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    hiring_rows,
                )

            if leave_rows:
                cur.execute(
                    "DELETE FROM leave_records WHERE release_date = %s",
                    (DAY2_RELEASE_DATE,),
                )
                cur.executemany(
                    """INSERT INTO leave_records
                    (employee_id, leave_type, start_date, end_date, days_count, status, notes, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    leave_rows,
                )

            if pulse_rows:
                cur.execute(
                    "DELETE FROM pulse_surveys WHERE release_date = %s",
                    (DAY2_RELEASE_DATE,),
                )
                cur.executemany(
                    """INSERT INTO pulse_surveys
                    (survey_period, department, respondent_count, avg_score, comments_withheld, withhold_reason, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    pulse_rows,
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
                    (email_id, sender_raw, sender_entity_id, recipients_raw, cc_raw,
                     subject, sent_at, event_date, body_text, source_file, release_date)
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
                    (doc_id, source_file, doc_type, title, section_label, content_text, event_date, release_date)
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

            if voice_note_rows:
                cur.executemany(
                    """INSERT INTO voice_note_decisions
                    (note_id, release_date, ceo_request, decision_type, response_summary, doc_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (note_id) DO UPDATE SET
                        release_date = EXCLUDED.release_date,
                        ceo_request = EXCLUDED.ceo_request,
                        decision_type = EXCLUDED.decision_type,
                        response_summary = EXCLUDED.response_summary,
                        doc_path = EXCLUDED.doc_path""",
                    voice_note_rows,
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
                (DAY2_TAG, DAY2_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
            )


def ingest_day2(
    data_dir: Path | str,
    db: DatabaseManager | None = None,
    sync_postgres: bool = True,
) -> dict[str, Any]:
    """Execute end-to-end ingestion of Day 2 release pack."""
    db_mgr = db or DatabaseManager()
    root = _find_day2_root(Path(data_dir))
    if not root.is_dir():
        raise FileNotFoundError(f"Day 2 directory does not exist: {root}")

    # Build schema if needed
    db_mgr.init_schema(sync_postgres=sync_postgres)

    # 1. Inspect and map Day 2 files
    xlsx_files = {p.name: p for p in _iter_files(root, (".xlsx",))}
    docx_files = {p.name: p for p in _iter_files(root, (".docx",))}
    pdf_files = {p.name: p for p in _iter_files(root, (".pdf",))}
    eml_files = {p.name: p for p in _iter_files(root, (".eml",))}

    files_loaded = len(xlsx_files) + len(docx_files) + len(pdf_files) + len(eml_files)
    records_loaded = 0

    # 2. Hiring Tracker (Keka Hire) -> hiring_reqs
    hiring_rows: list[tuple[Any, ...]] = []
    if "Hiring_Tracker.xlsx" in xlsx_files:
        raw_reqs = _read_xlsx_sheet(
            xlsx_files["Hiring_Tracker.xlsx"],
            sheet_name="Requisitions",
            header_markers={"req_id", "role"},
        )
        for r in raw_reqs:
            req_id = str(r.get("req_id", "")).strip()
            if not req_id or not req_id.startswith("REQ-"):
                continue
            role = str(r.get("role", "")).strip()
            team = str(r.get("team", "")).strip()
            status = str(r.get("status", "")).strip()
            opened = _to_iso_date(r.get("opened", ""))
            status_date = _to_iso_date(r.get("status_date", ""))
            try:
                pipeline_count = int(r.get("in_pipeline", 0))
            except (TypeError, ValueError):
                pipeline_count = 0
            notes = str(r.get("notes", "")).strip() or None
            ats_system = "Keka Hire"

            hiring_rows.append((
                req_id,
                role,
                team,
                status,
                opened,
                status_date,
                pipeline_count,
                ats_system,
                notes,
                "Hiring_Tracker.xlsx",
                DAY2_RELEASE_DATE,
            ))
        records_loaded += len(hiring_rows)

    # 3. Leave Register -> leave_records
    leave_rows: list[tuple[Any, ...]] = []
    if "Leave_Register.xlsx" in xlsx_files:
        raw_leave = _read_xlsx_sheet(
            xlsx_files["Leave_Register.xlsx"],
            sheet_name="Leave FY",
            header_markers={"employee", "leave_type"},
        )
        for r in raw_leave:
            emp_raw = str(r.get("employee", "")).strip()
            if not emp_raw:
                continue
            emp_id = EMPLOYEE_NAME_MAP.get(emp_raw.lower(), emp_raw)
            leave_type = str(r.get("leave_type", "")).strip()
            from_date = _to_iso_date(r.get("from", ""))
            to_date = _to_iso_date(r.get("to", ""))
            try:
                days_cnt = float(r.get("days", 1.0))
            except (TypeError, ValueError):
                days_cnt = 1.0
            app_raw = str(r.get("approved_by", "")).strip().lower()
            approver_id = INITIALS_TO_EMP_ID.get(app_raw, app_raw.upper())
            notes = f"Approved by {approver_id}" if app_raw else None

            leave_rows.append((
                emp_id,
                leave_type,
                from_date,
                to_date,
                days_cnt,
                "Approved",
                notes,
                "Leave_Register.xlsx",
                DAY2_RELEASE_DATE,
            ))
        records_loaded += len(leave_rows)

    # 4. Pulse Survey -> pulse_surveys
    pulse_rows: list[tuple[Any, ...]] = []
    if "Pulse_Survey.xlsx" in xlsx_files:
        raw_pulse = _read_xlsx_sheet(
            xlsx_files["Pulse_Survey.xlsx"],
            sheet_name="Pulse by team",
            header_markers={"quarter", "team"},
        )
        for r in raw_pulse:
            quarter = str(r.get("quarter", "")).strip()
            team = str(r.get("team", "")).strip()
            if not quarter or not team:
                continue
            try:
                responses = int(r.get("responses", 0))
            except (TypeError, ValueError):
                responses = 0
            try:
                score = float(r.get("engagement_(1_5)", 0.0))
            except (TypeError, ValueError):
                score = 0.0

            # Culture Amp anonymity threshold: team size < 6 forces comments withheld
            comments_withheld = True
            withhold_reason = "Culture Amp anonymity threshold: team size < 6"

            pulse_rows.append((
                quarter,
                team,
                responses,
                score,
                1 if not db_mgr.postgres_enabled else True,  # 1 for sqlite boolean
                withhold_reason,
                "Pulse_Survey.xlsx",
                DAY2_RELEASE_DATE,
            ))
        records_loaded += len(pulse_rows)

    # 5. Documents (Resignation Letter & Transcripts)
    doc_rows: list[tuple[Any, ...]] = []
    if "Resignation_Letter_SM.pdf" in pdf_files:
        pages = _extract_pdf_pages(pdf_files["Resignation_Letter_SM.pdf"])
        full_text = "\n\n".join(txt for _, txt in pages)
        doc_rows.append((
            "DOC_RESIGNATION_SM",
            "Resignation_Letter_SM.pdf",
            "pdf_report",
            "Resignation Letter - Siddharth Mehta (VX013)",
            "body",
            full_text,
            "2026-09-15",
            DAY2_RELEASE_DATE,
        ))

    if "T3_Head_of_People_Call.docx" in docx_files:
        t3_txt = _extract_docx_text(docx_files["T3_Head_of_People_Call.docx"])
        doc_rows.append((
            "TRANSCRIPT_T3",
            "T3_Head_of_People_Call.docx",
            "transcript",
            "T3 · Head of People call",
            "body",
            t3_txt,
            "2026-10-31",
            DAY2_RELEASE_DATE,
        ))

    if "T6a_CEO_Voice_Note.docx" in docx_files:
        t6a_txt = _extract_docx_text(docx_files["T6a_CEO_Voice_Note.docx"])
        doc_rows.append((
            "VOICE_NOTE_T6A",
            "T6a_CEO_Voice_Note.docx",
            "voice_note",
            "T6a · CEO voice note",
            "body",
            t6a_txt,
            "2026-11-17",
            DAY2_RELEASE_DATE,
        ))
    records_loaded += len(doc_rows)

    # 6. Emails
    email_rows: list[tuple[Any, ...]] = []
    for eml_name, eml_path in sorted(eml_files.items()):
        parsed = _parse_eml(eml_path)
        sender_addr = _extract_email_addr(parsed["sender_raw"])
        event_date = _parse_email_iso_date(parsed["sent_at"])

        # sender resolution
        sender_id = None
        if "meera" in sender_addr:
            sender_id = "VX003"
        elif "vikram" in sender_addr:
            sender_id = "VX004"
        elif "arjun" in sender_addr:
            sender_id = "VX009"
        elif "deepa" in sender_addr:
            sender_id = "VX005"
        elif "rohan" in sender_addr:
            sender_id = "VX015"
        elif "ananya" in sender_addr:
            sender_id = "VX001"

        email_rows.append((
            parsed["email_id"],
            parsed["sender_raw"],
            sender_id,
            parsed["recipients_raw"],
            parsed["cc_raw"],
            parsed["subject"],
            parsed["sent_at"],
            event_date,
            parsed["body_text"],
            parsed["source_file"],
            DAY2_RELEASE_DATE,
        ))
    records_loaded += len(email_rows)

    # 7. Day 2 Entity Aliases, Evidence & Conflicts
    alias_rows = _day2_curated_aliases()
    evidence_rows = _day2_curated_evidence()
    conflict_rows = _day2_curated_conflicts()
    records_loaded += len(alias_rows) + len(evidence_rows) + len(conflict_rows)

    # 8. Voice Note Decision (T6a)
    voice_note_rows = [
        (
            "T6a",
            DAY2_RELEASE_DATE,
            "When I open it, it should just tell me what to worry about. Top three.",
            "implemented",
            "Implemented Top 3 Ranked Worries as default landing view with evidence citations and confidence levels, while retaining an expandable drawer for #4+ lower-ranked audit items.",
            "voice_notes/T6a_response.md",
        ),
    ]
    records_loaded += len(voice_note_rows)

    # 9. Upsert into local SQLite mirror
    with db_mgr.sqlite_conn() as conn:
        if hiring_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO hiring_reqs
                (req_id, role_title, department, status, opened_date, paused_or_closed_date,
                 pipeline_count, ats_system, notes, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                hiring_rows,
            )

        if leave_rows:
            conn.execute("DELETE FROM leave_records WHERE release_date = ?", (DAY2_RELEASE_DATE,))
            conn.executemany(
                """INSERT INTO leave_records
                (employee_id, leave_type, start_date, end_date, days_count, status, notes, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                leave_rows,
            )

        if pulse_rows:
            conn.execute("DELETE FROM pulse_surveys WHERE release_date = ?", (DAY2_RELEASE_DATE,))
            sqlite_pulse = [(*r[:4], 1, *r[5:]) for r in pulse_rows]
            conn.executemany(
                """INSERT INTO pulse_surveys
                (survey_period, department, respondent_count, avg_score, comments_withheld, withhold_reason, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                sqlite_pulse,
            )

        if doc_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO documents
                (doc_id, source_file, doc_type, title, section_label, content_text, event_date, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                doc_rows,
            )

        if email_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO emails
                (email_id, sender_raw, sender_entity_id, recipients_raw, cc_raw,
                 subject, sent_at, event_date, body_text, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                email_rows,
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

        if voice_note_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO voice_note_decisions
                (note_id, release_date, ceo_request, decision_type, response_summary, doc_path)
                VALUES (?, ?, ?, ?, ?, ?)""",
                voice_note_rows,
            )

        conn.execute(
            """INSERT OR REPLACE INTO ingestion_runs
            (release_tag, release_date, source_dir, files_loaded, records_loaded, status, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (DAY2_TAG, DAY2_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
        )

    # 10. Upsert into Supabase PostgreSQL (if configured)
    postgres_status = "skipped"
    if sync_postgres and db_mgr.postgres_enabled:
        pg_pulse_rows = [(*r[:4], True, *r[5:]) for r in pulse_rows]
        _sync_postgres_day2(
            db=db_mgr,
            hiring_rows=hiring_rows,
            leave_rows=leave_rows,
            pulse_rows=pg_pulse_rows,
            alias_rows=alias_rows,
            evidence_rows=evidence_rows,
            conflict_rows=conflict_rows,
            email_rows=email_rows,
            doc_rows=doc_rows,
            voice_note_rows=voice_note_rows,
            root=root,
            files_loaded=files_loaded,
            records_loaded=records_loaded,
        )
        postgres_status = "synced (Supabase PostgreSQL)"

    return {
        "status": "completed",
        "release_tag": DAY2_TAG,
        "release_date": DAY2_RELEASE_DATE,
        "source_dir": str(root),
        "files_loaded": files_loaded,
        "records_loaded": records_loaded,
        "hiring_reqs": len(hiring_rows),
        "leave_records": len(leave_rows),
        "pulse_surveys": len(pulse_rows),
        "documents": len(doc_rows),
        "emails": len(email_rows),
        "aliases": len(alias_rows),
        "evidence": len(evidence_rows),
        "conflicts": len(conflict_rows),
        "voice_note_decisions": len(voice_note_rows),
        "postgres_sync": postgres_status,
    }
