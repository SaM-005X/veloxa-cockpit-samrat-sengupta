"""Day 3 ingestion pipeline (`Day3_Wed_18Nov`, release_date = 2026-11-18).

Parses raw Day 3 Engineering exports (Jira, Git, PagerDuty Incidents, On-Call Rota),
Documents (Atlas Launch Kit, Invoice PIS-114, Email Printouts), Emails (04, 05, 08, 09),
and Transcripts (T4, T5, T6b) into local SQLite (`veloxa.db`) and Supabase PostgreSQL.
"""

from __future__ import annotations

import csv
import email
import json
import re
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from agents.persona import PERSONA_DEFINITIONS
from db.database import DatabaseManager
from ingest.temporal import RELEASE_DATES

DAY3_TAG = "Day3_Wed_18Nov"
DAY3_RELEASE_DATE = RELEASE_DATES[DAY3_TAG]
IST_TZ = timezone(timedelta(hours=5, minutes=30))

JIRA_INITIALS_MAP: dict[str, str] = {
    "pn": "VX007",
    "ad": "VX009",
    "rv": "VX018",
    "sk": "VX012",
    "vm": "VX004",
    "vikram": "VX004",
}

GIT_EMAIL_MAP: dict[str, tuple[str, str]] = {
    "priya.n@veloxa.in": ("VX007", "Priya Nair"),
    "pnair@users.noreply.github.com": ("VX007", "Priya Nair"),
    "arjun@veloxa.in": ("VX009", "Arjun Das"),
    "rahul.v@veloxa.in": ("VX018", "Rahul Verma"),
    "sneha.k@veloxa.in": ("VX012", "Sneha Kulkarni"),
    "vikram@veloxa.in": ("VX004", "Vikram Menon"),
}

OPS_NAME_MAP: dict[str, str] = {
    "sneha": "VX012",
    "snehal": "EXT001",
    "s. patil": "EXT001",
    "arjun": "VX009",
    "priya": "VX007",
    "rahul": "VX018",
    "vikram": "VX004",
}


def _normalize_col(col: Any) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


def _find_day3_root(data_dir: Path) -> Path:
    if (data_dir / DAY3_TAG).is_dir():
        return data_dir / DAY3_TAG
    return data_dir


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes
    )


def _to_iso_date(val: Any) -> str:
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
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _parse_email_iso_date(sent_at: str) -> str:
    if not sent_at:
        return ""
    try:
        return parsedate_to_datetime(sent_at).date().isoformat()
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


def _day3_curated_aliases() -> list[tuple[Any, ...]]:
    """Verified Day 3 aliases strictly from Day3_Wed_18Nov artifacts (no duplicate Day 1-2 pairs)."""
    return [
        # Git & Jira engineering handles
        ("pnair@users.noreply.github.com", "VX007", "person", "Priya Nair", "Secondary GitHub noreply email in git_log.csv (163 commits)", DAY3_RELEASE_DATE),
        ("PN", "VX007", "person", "Priya Nair", "Jira Assignee initials in Jira_Export_ATLAS.xlsx", DAY3_RELEASE_DATE),
        ("AD", "VX009", "person", "Arjun Das", "Jira Assignee initials in Jira_Export_ATLAS.xlsx", DAY3_RELEASE_DATE),
        ("RV", "VX018", "person", "Rahul Verma", "Jira Assignee initials in Jira_Export_ATLAS.xlsx", DAY3_RELEASE_DATE),
        ("SK", "VX012", "person", "Sneha Kulkarni", "Jira Assignee initials in Jira_Export_ATLAS.xlsx", DAY3_RELEASE_DATE),
        ("vikram", "VX004", "person", "Vikram Menon", "Jira Versions Changed By handle in Jira_Export_ATLAS.xlsx", DAY3_RELEASE_DATE),
        # Transcript & Ops name aliases
        ("Nikhil B.", "VX006", "person", "Nikhil Bose", "Speaker label in T4_Head_of_Marketing_Call.docx", DAY3_RELEASE_DATE),
        ("Vikram M.", "VX004", "person", "Vikram Menon", "Speaker label in T5_VP_Engineering_Call.docx", DAY3_RELEASE_DATE),
        ("Ayesha", "VX011", "person", "Aisha Khan", "ASR phonetic spelling in T4_Head_of_Marketing_Call.docx", DAY3_RELEASE_DATE),
        ("Manoj", "VX002", "person", "Manoj Kumar", "Sales Lead referenced in T4_Head_of_Marketing_Call.docx", DAY3_RELEASE_DATE),
        ("Sneha", "VX012", "person", "Sneha Kulkarni", "FTE SRE in Incidents_Aug-Oct_2026.xlsx, OnCall_Rota.xlsx, 08.eml, and T5", DAY3_RELEASE_DATE),
        ("Snehal", "EXT001", "contractor", "S. Patil (Patil Infra Services)", "On-call contractor in Incidents & OnCall_Rota; distinct from Sneha Kulkarni (VX012)", DAY3_RELEASE_DATE),
        ("S. Patil", "EXT001", "contractor", "S. Patil (Patil Infra Services)", "Contractor named on Invoice_PIS-114.pdf", DAY3_RELEASE_DATE),
        ("PATIL INFRA SERVICES", "EXT001", "vendor", "Patil Infra Services", "Invoice vendor header on Invoice_PIS-114.pdf", DAY3_RELEASE_DATE),
        ("Arjun", "VX009", "person", "Arjun Das", "Responder/on-call name in Incidents_Aug-Oct_2026.xlsx and OnCall_Rota.xlsx", DAY3_RELEASE_DATE),
        ("Priya", "VX007", "person", "Priya Nair", "On-call secondary / email author in OnCall_Rota.xlsx, 04.eml, 09.eml", DAY3_RELEASE_DATE),
        ("Rahul", "VX018", "person", "Rahul Verma", "Referenced in 04.eml and T5_VP_Engineering_Call.docx", DAY3_RELEASE_DATE),
        # Tool mishearings / ASR spacing in T4 & T5
        ("Linked in campaign manager", "TOOL_LINKEDIN_ADS", "tool", "LinkedIn Campaign Manager", "ASR spacing in T4_Head_of_Marketing_Call.docx (not exported)", DAY3_RELEASE_DATE),
        ("pager duty", "TOOL_PAGERDUTY", "tool", "PagerDuty", "ASR spacing in T5_VP_Engineering_Call.docx", DAY3_RELEASE_DATE),
        ("Con fluence", "TOOL_CONFLUENCE", "tool", "Confluence", "ASR spacing in T5_VP_Engineering_Call.docx (not exported)", DAY3_RELEASE_DATE),
        ("Linear", "TOOL_LINEAR", "tool", "Linear", "Issue tracker briefly trialed per T5_VP_Engineering_Call.docx (not exported)", DAY3_RELEASE_DATE),
    ]


def _day3_curated_evidence() -> list[tuple[Any, ...]]:
    """Verified atomic Day 3 evidence items strictly from Day3_Wed_18Nov."""
    return [
        (
            "E036",
            "Jira_Export_ATLAS.xlsx",
            "export",
            "Versions!row2",
            "Jira Versions shows Atlas GA release target was pushed from 2026-09-15 to 2026-12-15 on 2026-09-02 by vikram (VX004).",
            json.dumps(["VX004", "PROJ_ATLAS_V3", "TOOL_JIRA"]),
            "2026-09-02",
            DAY3_RELEASE_DATE,
            "High",
            "CG_ATLAS_DATE",
        ),
        (
            "E037",
            "Jira_Export_ATLAS.xlsx",
            "export",
            "Issues!rows4-65",
            "ATLAS project contains 62 stories (233 story points) across 5 epics: 35 Done (118 pts, 50.6%), 8 In Progress (38 pts), and 19 To Do (77 pts).",
            json.dumps(["PROJ_ATLAS_V3", "TOOL_JIRA"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "High",
            "CG_ATLAS_DATE",
        ),
        (
            "E038",
            "Jira_Export_ATLAS.xlsx",
            "export",
            "Issues!rows4-65",
            "Priya Nair (PN, VX007) is assigned 35 of 62 Jira stories (56.5%, 131/233 story points), including 12/12 stories (100%) on ATLAS-2 Real-time re-routing (5 Done, 2 In Progress, 5 To Do).",
            json.dumps(["VX007", "PROJ_ATLAS_V3", "TOOL_JIRA"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "High",
            "CG_PRIYA_LOAD",
        ),
        (
            "E039",
            "Jira_Export_ATLAS.xlsx",
            "export",
            "Issues!rows4-65",
            "Remaining Jira assignments: Arjun Das (VX009) owns 12/12 ATLAS-4 UI stories (10 Done, 2 To Do); Rahul Verma (VX018) owns 11 stories across ATLAS-1/3 (4 Done, 1 In Progress, 6 To Do); Sneha Kulkarni (VX012) has 4 ATLAS-5 perf stories all To Do; Vikram Menon (VX004) has 0 stories.",
            json.dumps(["VX009", "VX018", "VX012", "VX004", "PROJ_ATLAS_V3"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "High",
            "CG_PRIYA_LOAD",
        ),
        (
            "E040",
            "git_log.csv",
            "export",
            "rows 1-1453",
            "Across 1,453 git commits (Nov 2025-Oct 2026 IST), Priya Nair (VX007) authored 588 commits (40.5%: 425 via priya.n@veloxa.in + 163 via pnair@users.noreply.github.com), all in atlas-engine, including 103 late-night (22:00-05:59 IST) and 40 weekend commits starting June 2026 (0 before June). All other engineers had 0 late-night and 0 weekend commits.",
            json.dumps(["VX007", "TOOL_GITHUB"]),
            "2026-10-30",
            DAY3_RELEASE_DATE,
            "High",
            "CG_PRIYA_LOAD",
        ),
        (
            "E041",
            "git_log.csv",
            "export",
            "rows 1-1453",
            "Git commit breakdown for other engineers: Arjun Das (VX009) 348 commits (planner-web), Rahul Verma (VX018) 237 (120 atlas-api, 117 atlas-engine), Sneha Kulkarni (VX012) 235 (120 infra, 115 atlas-engine), Vikram Menon (VX004) 45 (23 atlas-engine, 22 planner-web).",
            json.dumps(["VX009", "VX018", "VX012", "VX004", "TOOL_GITHUB"]),
            "2026-10-30",
            DAY3_RELEASE_DATE,
            "High",
            "CG_PRIYA_LOAD",
        ),
        (
            "E042",
            "Incidents_Aug-Oct_2026.xlsx",
            "export",
            "Incidents!rows4-14",
            "11 PagerDuty incidents occurred Aug-Oct 2026: all 3 August SEV1 outages (INC-201 Aug 4, INC-203 Aug 13, INC-205 Aug 22 on routing-api) were handled by Sneha Kulkarni (VX012). Contractor Snehal (EXT001) handled 4 incidents (3 SEV2 routing-api, 1 SEV3 traffic-ingest) starting Aug 27; Arjun handled 1 SEV2 (INC-202).",
            json.dumps(["VX012", "EXT001", "VX009", "TOOL_PAGERDUTY"]),
            "2026-10-21",
            DAY3_RELEASE_DATE,
            "High",
            "CG_SNEHA_SNEHAL",
        ),
        (
            "E043",
            "OnCall_Rota.xlsx",
            "export",
            "On-call!rows4-20",
            "Across 17 weeks (Jul 6-Oct 26, 2026), Sneha (VX012) covered 6 consecutive weeks as solo Primary on-call (Jul 6-Aug 10) before contractor Snehal (EXT001) joined the rota on 2026-08-17; overall Sneha covered 11 Primary / 6 Secondary weeks and Snehal covered 6 Primary / 5 Secondary weeks.",
            json.dumps(["VX012", "EXT001", "VX009", "VX007"]),
            "2026-10-26",
            DAY3_RELEASE_DATE,
            "High",
            "CG_SNEHA_SNEHAL",
        ),
        (
            "E044",
            "Invoice_PIS-114.pdf",
            "document",
            "page_1",
            "Patil Infra Services (Baner Road, Pune) Invoice PIS-114 dated 2026-10-01 bills Rs. 1,41,600 (Rs. 1,20,000 + 18% IGST Rs. 21,600) for September 2026 on-call SRE support by S. Patil (EXT001), noting previous pro-rata invoice PIS-108 (18-31 Aug, GL JV-0902 Rs. 70,800) was settled.",
            json.dumps(["EXT001"]),
            "2026-10-01",
            DAY3_RELEASE_DATE,
            "High",
            "CG_SNEHA_SNEHAL",
        ),
        (
            "E045",
            "Atlas_Launch_Kit_v1.pdf",
            "document",
            "page_1",
            "Siddharth Mehta (VX013) completed Atlas_Launch_Kit_v1.pdf on 2026-07-21 (sales launch deck Ready, website page Ready unpublished, 3 customer emails Ready, press note Draft, planned 22 Sep) and emailed Nikhil/Vikram on 2026-07-22 (05.eml) asking engineering for a launch date.",
            json.dumps(["VX013", "VX006", "VX004", "PROJ_ATLAS_V3"]),
            "2026-07-22",
            DAY3_RELEASE_DATE,
            "High",
            "CG_LAUNCH_KIT",
        ),
        (
            "E046",
            "04.eml",
            "email",
            "04.eml",
            "Vikram Menon emailed Ananya Rao on 2026-06-02 outlining the Atlas plan: Priya leads core engine and re-routing, Rahul on API, Arjun on UI, Sneha on hardening; '15 Sep GA is achievable if the two backend hires land by July.'",
            json.dumps(["VX004", "VX001", "VX007", "VX018", "VX009", "VX012", "PROJ_ATLAS_V3"]),
            "2026-06-02",
            DAY3_RELEASE_DATE,
            "High",
            "CG_ATLAS_DATE",
        ),
        (
            "E047",
            "08.eml",
            "email",
            "08.eml",
            "Sneha Kulkarni emailed Vikram Menon on 2026-08-24 after the third August SEV1: 'I'm pausing the Atlas perf tickets to stabilise routing-api. The contractor starts on the rota this week.'",
            json.dumps(["VX012", "VX004", "EXT001"]),
            "2026-08-24",
            DAY3_RELEASE_DATE,
            "High",
            "CG_SNEHA_SNEHAL",
        ),
        (
            "E048",
            "09.eml",
            "email",
            "09.eml",
            "Priya Nair emailed Vikram Menon on 2026-09-01 at 23:47 IST (the night before Atlas GA moved to Dec 15): 'Can we talk about Atlas ownership sometime this week? Need some time with you.'",
            json.dumps(["VX007", "VX004", "PROJ_ATLAS_V3"]),
            "2026-09-01",
            DAY3_RELEASE_DATE,
            "High",
            "CG_PRIYA_LOAD",
        ),
        (
            "E049",
            "T4_Head_of_Marketing_Call.docx",
            "transcript",
            "P4, P8, P12",
            "Nikhil Bose (VX006) claims half-year marketing spend is 'one point eight' (Rs. 18L) and summit budget 'went a little over, nothing crazy', contradicting Zoho Books GL Rs. 14,26,620 (a Rs. 3,73,380 gap); Ayesha (VX011) is assigned to send the campaign sheet to finance.",
            json.dumps(["VX006", "VX011"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "Low",
            "CG_MKT_SPEND",
        ),
        (
            "E050",
            "T4_Head_of_Marketing_Call.docx",
            "transcript",
            "P4, P7, P9, P10",
            "Nikhil calls the September summit 'our best quarter ever for pipeline' and dismisses Manoj Kumar's (VX002) feedback that 'summit leads are cold'; notes HubSpot and LinkedIn Campaign Manager (unexported) are used and LinkedIn is 'a brand play'.",
            json.dumps(["VX006", "VX002", "TOOL_HUBSPOT", "TOOL_LINKEDIN_ADS"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "Low",
            "CG_MKT_SPEND",
        ),
        (
            "E051",
            "T5_VP_Engineering_Call.docx",
            "transcript",
            "P2, P4, P9, P10",
            "Vikram Menon (VX004) tells Ananya Atlas v3 is 'on track, maybe a couple of weeks of buffer needed', board date is 'still September-ish', disputes overload ('everyone's busy, that's startups'), and claims 'Pria has been doing late nights but she likes it'. Call has a ~4 min audio gap (11:20-15:30).",
            json.dumps(["VX004", "VX001", "VX007", "PROJ_ATLAS_V3"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "Low",
            "CG_ATLAS_DATE",
        ),
        (
            "E052",
            "T5_VP_Engineering_Call.docx",
            "transcript",
            "P4, P6, P13",
            "Vikram claims August incidents 'pulled Snehal off' and assigns August postmortems on Confluence to 'Snehal', conflating FTE SRE Sneha Kulkarni (VX012) with contractor S. Patil (EXT001) who started Aug 18.",
            json.dumps(["VX004", "VX012", "EXT001", "TOOL_CONFLUENCE"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
            "Low",
            "CG_SNEHA_SNEHAL",
        ),
        (
            "E053",
            "Email_Printouts.pdf",
            "document",
            "pages 1-2",
            "Email_Printouts.pdf compiles email threads 01 through 11 in IST; verified identical in headers, timestamps, and body text to individual files 01.eml-11.eml.",
            json.dumps(["VX001", "VX003", "VX004", "VX005", "VX006", "VX007", "VX009", "VX010", "VX012", "VX013", "VX014", "VX018"]),
            "2026-09-29",
            DAY3_RELEASE_DATE,
            "High",
            None,
        ),
        (
            "E054",
            "T6b_CEO_Voice_Note.docx",
            "voice_note",
            "P3",
            "CEO Voice Note T6b states: 'So, marketing will report to the new CRO from next month. Or the month after, still finalising. Make sure the thing doesn't break when we move people around.'",
            json.dumps(["VX001", "VX006", "VX011"]),
            "2026-11-18",
            DAY3_RELEASE_DATE,
            "High",
            None,
        ),
    ]


def _day3_curated_conflicts() -> list[tuple[Any, ...]]:
    """Verified Day 3 cross-source contradictions strictly from Day3_Wed_18Nov."""
    return [
        (
            "C09",
            "Atlas v3 GA Date & Schedule Reality (T5 Vikram vs Jira)",
            "E051",
            "E036",
            "In T5, Vikram Menon tells Ananya that Atlas v3 is 'on track, maybe a couple of weeks of buffer needed' and board date is 'still September-ish'. However, Jira_Export_ATLAS.xlsx (Versions tab) proves Vikram himself changed Atlas GA from 2026-09-15 to 2026-12-15 on 2026-09-02 (a 3-month slip), and only 35/62 stories (118/233 story points = 50.6%) are Done.",
            "resolved",
            "Trust Jira_Export_ATLAS.xlsx: Atlas GA was pushed to 2026-12-15 by Vikram on 2026-09-02, with 49.4% of story points still In Progress or To Do.",
            DAY3_RELEASE_DATE,
        ),
        (
            "C10",
            "Priya Nair Workload & Burnout (T5 Optimism vs Git/Jira/Leave/09.eml)",
            "E051",
            "E040",
            "Vikram asserts in T5 that 'everyone's busy, that's startups' and 'Pria has been doing late nights but she likes it'. In contrast, Jira shows Priya (VX007) owns 35/62 stories (56.5%, 100% of ATLAS-2), git_log.csv shows she authored 588/1,453 commits including all 103 late-night and 40 weekend commits (all starting June 2026, peaking at 29 late-night + 17 weekend in August), she emailed Vikram at 23:47 IST on Sep 1 asking to discuss Atlas ownership (09.eml), and she took 5 Sep afternoon leaves (E026).",
            "open",
            "Critical single-point-of-failure burnout and retention risk: hard engineering and leave telemetry directly refute Vikram's claim that Priya is fine with late-night heroics.",
            DAY3_RELEASE_DATE,
        ),
        (
            "C11",
            "Sneha (VX012) vs Snehal (EXT001) Identity & August Postmortems",
            "E052",
            "E042",
            "In T5, Vikram attributes August incidents to 'Snehal', assigns August postmortems to 'Snehal', and is unsure whether 'Sneha' is the same person. Records prove Sneha Kulkarni (VX012, FTE SRE) handled 6 solo primary on-call weeks and all 3 August SEV1s (INC-201, INC-203, INC-205), whereas Snehal / S. Patil (EXT001, Patil Infra Services contractor) only started on 2026-08-18 (PIS-108, OnCall_Rota, 08.eml).",
            "resolved",
            "Distinct entities: Sneha Kulkarni (VX012) is the FTE SRE who resolved the 3 Aug SEV1s and paused ATLAS-5 perf work; Snehal / S. Patil (EXT001) is the external Pune contractor hired mid-August.",
            DAY3_RELEASE_DATE,
        ),
        (
            "C12",
            "Marketing Half-Year Spend & Pipeline Quality (T4 Nikhil vs GL & Sales)",
            "E049",
            "E018",
            "Nikhil claims in T4 that half-year marketing spend is 'one point eight' (Rs. 18L) and summit pipeline is 'our best quarter ever'. Zoho Books GL_Export books Rs. 14,26,620 across Marketing cost centers (MKT-PS Google Ads Rs. 4,23,620 + MKT-EVT Summit Rs. 10,03,000), leaving a Rs. 3,73,380 gap (and JV-0918 Rs. 38,940 Sapphire Residency Hotel is SAL-TRV). Meanwhile Sales Lead Manoj reports summit leads are 'cold', and HubSpot/LinkedIn exports are absent.",
            "open",
            "Unreconciled Rs. 3,73,380 Marketing spend discrepancy and disputed summit lead quality; requires Ayesha's campaign sheet reconciliation with Finance (T4 action item).",
            DAY3_RELEASE_DATE,
        ),
        (
            "C13",
            "Atlas Launch Kit Readiness vs Engineering Slip & PMM Exit",
            "E045",
            "E036",
            "Siddharth Mehta (VX013) finished Atlas_Launch_Kit_v1.pdf on 2026-07-21 (05.eml) planning a 22 Sep launch TBC with engineering, while Vikram pushed Atlas GA to 2026-12-15 on 2026-09-02 without giving Marketing a firm launch date—contributing directly to Siddharth's resignation on 2026-09-15.",
            "resolved",
            "Cross-functional launch breakdown confirmed: completed July launch kit sat unpublished due to engineering schedule slips and missing executive communication.",
            DAY3_RELEASE_DATE,
        ),
    ]


def _build_agent_profile_rows() -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for emp_id, pdef in sorted(PERSONA_DEFINITIONS.items()):
        rows.append((
            emp_id,
            pdef["visibility_scope"],
            f"Point-in-time dynamic profile grounded in Veloxa data room ({DAY3_RELEASE_DATE}).",
            pdef["assumed_personal_context"],
        ))
    return rows


def _sync_postgres_day3(
    db: DatabaseManager,
    jira_version_rows: list[tuple[Any, ...]],
    jira_issue_rows: list[tuple[Any, ...]],
    git_rows: list[tuple[Any, ...]],
    incident_rows: list[tuple[Any, ...]],
    oncall_rows: list[tuple[Any, ...]],
    alias_rows: list[tuple[Any, ...]],
    evidence_rows: list[tuple[Any, ...]],
    conflict_rows: list[tuple[Any, ...]],
    email_rows: list[tuple[Any, ...]],
    doc_rows: list[tuple[Any, ...]],
    agent_profile_rows: list[tuple[Any, ...]],
    voice_note_rows: list[tuple[Any, ...]],
    root: Path,
    files_loaded: int,
    records_loaded: int,
) -> None:
    """Upsert Day 3 records into Supabase PostgreSQL."""
    from psycopg2.extras import execute_values

    with db.postgres_conn() as pg_conn:
        with pg_conn.cursor() as cur:
            if jira_version_rows:
                cur.executemany(
                    """INSERT INTO jira_versions
                    (version_name, release_target_date, previous_target_date, last_updated_by,
                     last_updated_date, status, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (version_name) DO UPDATE SET
                        release_target_date = EXCLUDED.release_target_date,
                        previous_target_date = EXCLUDED.previous_target_date,
                        last_updated_by = EXCLUDED.last_updated_by,
                        last_updated_date = EXCLUDED.last_updated_date,
                        status = EXCLUDED.status,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    jira_version_rows,
                )

            if jira_issue_rows:
                execute_values(
                    cur,
                    """INSERT INTO jira_issues
                    (issue_key, issue_type, epic_key, summary, status, assignee_id,
                     story_points, created_date, updated_date, source_file, release_date)
                    VALUES %s
                    ON CONFLICT (issue_key) DO UPDATE SET
                        issue_type = EXCLUDED.issue_type,
                        epic_key = EXCLUDED.epic_key,
                        summary = EXCLUDED.summary,
                        status = EXCLUDED.status,
                        assignee_id = EXCLUDED.assignee_id,
                        story_points = EXCLUDED.story_points,
                        created_date = EXCLUDED.created_date,
                        updated_date = EXCLUDED.updated_date,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    jira_issue_rows,
                )

            if git_rows:
                execute_values(
                    cur,
                    """INSERT INTO git_commits
                    (commit_hash, author_name, author_email, canonical_entity_id, repo_name,
                     committed_at_ist, event_date, is_late_night, is_weekend, message, source_file, release_date)
                    VALUES %s
                    ON CONFLICT (commit_hash) DO UPDATE SET
                        author_name = EXCLUDED.author_name,
                        author_email = EXCLUDED.author_email,
                        canonical_entity_id = EXCLUDED.canonical_entity_id,
                        repo_name = EXCLUDED.repo_name,
                        committed_at_ist = EXCLUDED.committed_at_ist,
                        event_date = EXCLUDED.event_date,
                        is_late_night = EXCLUDED.is_late_night,
                        is_weekend = EXCLUDED.is_weekend,
                        message = EXCLUDED.message,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    git_rows,
                    page_size=500,
                )

            if incident_rows:
                cur.executemany(
                    """INSERT INTO incidents
                    (incident_id, severity, title, service, occurred_date, responder_ids,
                     status, summary, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (incident_id) DO UPDATE SET
                        severity = EXCLUDED.severity,
                        title = EXCLUDED.title,
                        service = EXCLUDED.service,
                        occurred_date = EXCLUDED.occurred_date,
                        responder_ids = EXCLUDED.responder_ids,
                        status = EXCLUDED.status,
                        summary = EXCLUDED.summary,
                        source_file = EXCLUDED.source_file,
                        release_date = EXCLUDED.release_date""",
                    incident_rows,
                )

            if oncall_rows:
                cur.execute("DELETE FROM oncall_rota WHERE release_date = %s", (DAY3_RELEASE_DATE,))
                cur.executemany(
                    """INSERT INTO oncall_rota
                    (week_start, week_end, primary_entity_id, secondary_entity_id, source_file, release_date)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                    oncall_rows,
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

            if agent_profile_rows:
                cur.executemany(
                    """INSERT INTO agent_profiles
                    (employee_id, visibility_scope, grounded_summary, assumed_personal_context)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (employee_id) DO UPDATE SET
                        visibility_scope = EXCLUDED.visibility_scope,
                        grounded_summary = EXCLUDED.grounded_summary,
                        assumed_personal_context = EXCLUDED.assumed_personal_context,
                        updated_at = CURRENT_TIMESTAMP""",
                    agent_profile_rows,
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
                (DAY3_TAG, DAY3_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
            )


def ingest_day3(
    data_dir: Path | str,
    db: DatabaseManager | None = None,
    sync_postgres: bool = True,
) -> dict[str, Any]:
    """Execute end-to-end ingestion of Day 3 release pack (`Day3_Wed_18Nov`)."""
    db_mgr = db or DatabaseManager()
    root = _find_day3_root(Path(data_dir))
    if not root.is_dir():
        raise FileNotFoundError(f"Day 3 directory does not exist: {root}")

    db_mgr.init_schema(sync_postgres=sync_postgres)

    xlsx_files = {p.name: p for p in _iter_files(root, (".xlsx",))}
    csv_files = {p.name: p for p in _iter_files(root, (".csv",))}
    docx_files = {p.name: p for p in _iter_files(root, (".docx",))}
    pdf_files = {p.name: p for p in _iter_files(root, (".pdf",))}
    eml_files = {p.name: p for p in _iter_files(root, (".eml",))}

    files_loaded = len(xlsx_files) + len(csv_files) + len(docx_files) + len(pdf_files) + len(eml_files)
    records_loaded = 0

    # 1. Jira_Export_ATLAS.xlsx -> jira_versions + jira_issues
    jira_version_rows: list[tuple[Any, ...]] = []
    jira_issue_rows: list[tuple[Any, ...]] = []
    if "Jira_Export_ATLAS.xlsx" in xlsx_files:
        jira_path = xlsx_files["Jira_Export_ATLAS.xlsx"]
        raw_versions = _read_xlsx_sheet(jira_path, "Versions", {"version", "release_date"})
        for r in raw_versions:
            vname = str(r.get("version", "")).strip()
            if not vname:
                continue
            changed_by_raw = str(r.get("changed_by", "")).strip()
            changed_by = JIRA_INITIALS_MAP.get(changed_by_raw.lower(), changed_by_raw)
            jira_version_rows.append((
                vname,
                _to_iso_date(r.get("release_date", "")),
                _to_iso_date(r.get("original_release_date", "")),
                changed_by,
                _to_iso_date(r.get("last_changed", "")),
                "Delayed",
                "Jira_Export_ATLAS.xlsx",
                DAY3_RELEASE_DATE,
            ))

        raw_issues = _read_xlsx_sheet(jira_path, "Issues", {"key", "summary"})
        for r in raw_issues:
            key = str(r.get("key", "")).strip()
            if not key or not key.startswith("ATLAS-"):
                continue
            assignee_raw = str(r.get("assignee", "")).strip()
            assignee_id = JIRA_INITIALS_MAP.get(assignee_raw.lower(), assignee_raw)
            try:
                pts = float(r.get("story_points", 0))
            except (TypeError, ValueError):
                pts = 0.0
            resolved_dt = _to_iso_date(r.get("resolved", ""))
            jira_issue_rows.append((
                key,
                str(r.get("type", "Story")).strip(),
                str(r.get("epic_link", "")).strip() or None,
                str(r.get("summary", "")).strip(),
                str(r.get("status", "")).strip(),
                assignee_id,
                pts,
                _to_iso_date(r.get("created", "")),
                resolved_dt or None,
                "Jira_Export_ATLAS.xlsx",
                DAY3_RELEASE_DATE,
            ))
    records_loaded += len(jira_version_rows) + len(jira_issue_rows)

    # 2. git_log.csv -> git_commits
    git_rows_sqlite: list[tuple[Any, ...]] = []
    git_rows_pg: list[tuple[Any, ...]] = []
    if "git_log.csv" in csv_files:
        with csv_files["git_log.csv"].open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                sha = str(r.get("sha", "")).strip()
                if not sha:
                    continue
                email_addr = str(r.get("author_email", "")).strip().lower()
                canonical_id, author_name = GIT_EMAIL_MAP.get(email_addr, ("", email_addr))
                committed_raw = str(r.get("committed_at", "")).strip()
                dt_utc = datetime.fromisoformat(committed_raw.replace("Z", "+00:00"))
                dt_ist = dt_utc.astimezone(IST_TZ)
                is_late = (dt_ist.hour >= 22) or (dt_ist.hour < 6)
                is_wknd = dt_ist.weekday() >= 5
                committed_ist_str = dt_ist.isoformat()
                event_date = dt_ist.date().isoformat()
                repo_name = str(r.get("repo", "")).strip()
                msg = str(r.get("message", "")).strip()

                git_rows_sqlite.append((
                    sha, author_name, email_addr, canonical_id or None, repo_name,
                    committed_ist_str, event_date, 1 if is_late else 0, 1 if is_wknd else 0,
                    msg, "git_log.csv", DAY3_RELEASE_DATE,
                ))
                git_rows_pg.append((
                    sha, author_name, email_addr, canonical_id or None, repo_name,
                    committed_ist_str, event_date, is_late, is_wknd,
                    msg, "git_log.csv", DAY3_RELEASE_DATE,
                ))
    records_loaded += len(git_rows_sqlite)

    # 3. Incidents_Aug-Oct_2026.xlsx -> incidents
    incident_rows: list[tuple[Any, ...]] = []
    if "Incidents_Aug-Oct_2026.xlsx" in xlsx_files:
        raw_inc = _read_xlsx_sheet(xlsx_files["Incidents_Aug-Oct_2026.xlsx"], "Incidents", {"id", "severity"})
        for r in raw_inc:
            inc_id = str(r.get("id", "")).strip()
            if not inc_id or not inc_id.startswith("INC-"):
                continue
            sev = str(r.get("severity", "")).strip()
            opened = str(r.get("opened", "")).strip()
            resolved = str(r.get("resolved", "")).strip()
            service = str(r.get("service", "")).strip()
            resp_raw = str(r.get("responder", "")).strip()
            resp_id = OPS_NAME_MAP.get(resp_raw.lower(), resp_raw)
            occurred_date = _to_iso_date(opened)
            summary = f"Opened {opened}; Resolved {resolved}; Responder: {resp_raw} ({resp_id})"
            incident_rows.append((
                inc_id,
                sev,
                f"{sev} on {service}",
                service,
                occurred_date,
                resp_id,
                "Resolved" if resolved else "Open",
                summary,
                "Incidents_Aug-Oct_2026.xlsx",
                DAY3_RELEASE_DATE,
            ))
    records_loaded += len(incident_rows)

    # 4. OnCall_Rota.xlsx -> oncall_rota
    oncall_rows: list[tuple[Any, ...]] = []
    if "OnCall_Rota.xlsx" in xlsx_files:
        raw_rota = _read_xlsx_sheet(xlsx_files["OnCall_Rota.xlsx"], "On-call", {"week_of", "primary"})
        for r in raw_rota:
            week_start = _to_iso_date(r.get("week_of", ""))
            if not week_start:
                continue
            week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
            pri_raw = str(r.get("primary", "")).strip()
            sec_raw = str(r.get("secondary", "")).strip()
            pri_id = OPS_NAME_MAP.get(pri_raw.lower(), pri_raw)
            sec_id = OPS_NAME_MAP.get(sec_raw.lower(), sec_raw) if sec_raw else None
            oncall_rows.append((
                week_start,
                week_end,
                pri_id,
                sec_id,
                "OnCall_Rota.xlsx",
                DAY3_RELEASE_DATE,
            ))
    records_loaded += len(oncall_rows)

    # 5. Documents (PDFs & DOCX transcripts)
    doc_rows: list[tuple[Any, ...]] = []
    if "Atlas_Launch_Kit_v1.pdf" in pdf_files:
        txt = "\n\n".join(t for _, t in _extract_pdf_pages(pdf_files["Atlas_Launch_Kit_v1.pdf"]))
        doc_rows.append((
            "DOC_LAUNCH_KIT_V1",
            "Atlas_Launch_Kit_v1.pdf",
            "pdf_report",
            "Atlas Launch Kit v1 (Siddharth Mehta)",
            "body",
            txt,
            "2026-07-21",
            DAY3_RELEASE_DATE,
        ))
    if "Invoice_PIS-114.pdf" in pdf_files:
        txt = "\n\n".join(t for _, t in _extract_pdf_pages(pdf_files["Invoice_PIS-114.pdf"]))
        doc_rows.append((
            "DOC_INVOICE_PIS_114",
            "Invoice_PIS-114.pdf",
            "pdf_report",
            "Tax Invoice PIS-114 (Patil Infra Services)",
            "body",
            txt,
            "2026-10-01",
            DAY3_RELEASE_DATE,
        ))
    if "Email_Printouts.pdf" in pdf_files:
        txt = "\n\n".join(t for _, t in _extract_pdf_pages(pdf_files["Email_Printouts.pdf"]))
        doc_rows.append((
            "DOC_EMAIL_PRINTOUTS",
            "Email_Printouts.pdf",
            "pdf_report",
            "Email Export Printouts (Threads 01-11)",
            "body",
            txt,
            "2026-09-29",
            DAY3_RELEASE_DATE,
        ))
    if "T4_Head_of_Marketing_Call.docx" in docx_files:
        doc_rows.append((
            "TRANSCRIPT_T4",
            "T4_Head_of_Marketing_Call.docx",
            "transcript",
            "T4 · Head of Marketing call",
            "body",
            _extract_docx_text(docx_files["T4_Head_of_Marketing_Call.docx"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
        ))
    if "T5_VP_Engineering_Call.docx" in docx_files:
        doc_rows.append((
            "TRANSCRIPT_T5",
            "T5_VP_Engineering_Call.docx",
            "transcript",
            "T5 · VP Engineering call",
            "body",
            _extract_docx_text(docx_files["T5_VP_Engineering_Call.docx"]),
            "2026-10-31",
            DAY3_RELEASE_DATE,
        ))
    if "T6b_CEO_Voice_Note.docx" in docx_files:
        doc_rows.append((
            "VOICE_NOTE_T6B",
            "T6b_CEO_Voice_Note.docx",
            "voice_note",
            "T6b · CEO voice note",
            "body",
            _extract_docx_text(docx_files["T6b_CEO_Voice_Note.docx"]),
            "2026-11-18",
            DAY3_RELEASE_DATE,
        ))
    records_loaded += len(doc_rows)

    # 6. Emails (04.eml, 05.eml, 08.eml, 09.eml)
    email_rows: list[tuple[Any, ...]] = []
    for _, eml_path in sorted(eml_files.items()):
        parsed = _parse_eml(eml_path)
        sender_addr = _extract_email_addr(parsed["sender_raw"])
        event_date = _parse_email_iso_date(parsed["sent_at"])
        sender_id = None
        if "vikram" in sender_addr:
            sender_id = "VX004"
        elif "sid" in sender_addr:
            sender_id = "VX013"
        elif "sneha" in sender_addr:
            sender_id = "VX012"
        elif "priya" in sender_addr:
            sender_id = "VX007"
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
            DAY3_RELEASE_DATE,
        ))
    records_loaded += len(email_rows)

    # 7. Curated Day 3 Aliases, Evidence, Conflicts, Agent Profiles, and T6b Decision
    alias_rows = _day3_curated_aliases()
    evidence_rows = _day3_curated_evidence()
    conflict_rows = _day3_curated_conflicts()
    agent_profile_rows = _build_agent_profile_rows()
    voice_note_rows = [
        (
            "T6b",
            DAY3_RELEASE_DATE,
            "So, marketing will report to the new CRO from next month. Or the month after, still finalising. Make sure the thing doesn't break when we move people around.",
            "partial",
            "Implemented temporal reporting_lines resilience so future org moves never break historical queries; pushed back against executing a live Marketing reorg today without a confirmed CRO hire, reconciled Marketing GL spend (C12), or filled PMM REQ-016.",
            "voice_notes/T6b_response.md",
        ),
    ]
    records_loaded += (
        len(alias_rows)
        + len(evidence_rows)
        + len(conflict_rows)
        + len(agent_profile_rows)
        + len(voice_note_rows)
    )

    # 8. Upsert into SQLite mirror
    with db_mgr.sqlite_conn() as conn:
        if jira_version_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO jira_versions
                (version_name, release_target_date, previous_target_date, last_updated_by,
                 last_updated_date, status, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                jira_version_rows,
            )

        if jira_issue_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO jira_issues
                (issue_key, issue_type, epic_key, summary, status, assignee_id,
                 story_points, created_date, updated_date, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                jira_issue_rows,
            )

        if git_rows_sqlite:
            conn.executemany(
                """INSERT OR REPLACE INTO git_commits
                (commit_hash, author_name, author_email, canonical_entity_id, repo_name,
                 committed_at_ist, event_date, is_late_night, is_weekend, message, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                git_rows_sqlite,
            )

        if incident_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO incidents
                (incident_id, severity, title, service, occurred_date, responder_ids,
                 status, summary, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                incident_rows,
            )

        if oncall_rows:
            conn.execute("DELETE FROM oncall_rota WHERE release_date = ?", (DAY3_RELEASE_DATE,))
            conn.executemany(
                """INSERT INTO oncall_rota
                (week_start, week_end, primary_entity_id, secondary_entity_id, source_file, release_date)
                VALUES (?, ?, ?, ?, ?, ?)""",
                oncall_rows,
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

        if agent_profile_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO agent_profiles
                (employee_id, visibility_scope, grounded_summary, assumed_personal_context, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                agent_profile_rows,
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
            (DAY3_TAG, DAY3_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
        )

    # 9. Sync to Supabase PostgreSQL
    postgres_status = "skipped"
    if sync_postgres and db_mgr.postgres_enabled:
        _sync_postgres_day3(
            db=db_mgr,
            jira_version_rows=jira_version_rows,
            jira_issue_rows=jira_issue_rows,
            git_rows=git_rows_pg,
            incident_rows=incident_rows,
            oncall_rows=oncall_rows,
            alias_rows=alias_rows,
            evidence_rows=evidence_rows,
            conflict_rows=conflict_rows,
            email_rows=email_rows,
            doc_rows=doc_rows,
            agent_profile_rows=agent_profile_rows,
            voice_note_rows=voice_note_rows,
            root=root,
            files_loaded=files_loaded,
            records_loaded=records_loaded,
        )
        postgres_status = "synced (Supabase PostgreSQL)"

    return {
        "status": "completed",
        "release_tag": DAY3_TAG,
        "release_date": DAY3_RELEASE_DATE,
        "source_dir": str(root),
        "files_loaded": files_loaded,
        "records_loaded": records_loaded,
        "jira_versions": len(jira_version_rows),
        "jira_issues": len(jira_issue_rows),
        "git_commits": len(git_rows_sqlite),
        "incidents": len(incident_rows),
        "oncall_rota": len(oncall_rows),
        "documents": len(doc_rows),
        "emails": len(email_rows),
        "aliases": len(alias_rows),
        "evidence": len(evidence_rows),
        "conflicts": len(conflict_rows),
        "agent_profiles": len(agent_profile_rows),
        "voice_note_decisions": len(voice_note_rows),
        "postgres_sync": postgres_status,
    }
