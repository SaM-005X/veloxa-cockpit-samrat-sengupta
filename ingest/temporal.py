"""Temporal tagging & Point-in-Time isolation utilities.

Every source file in the Veloxa data room is assigned an official `release_date`
corresponding to the hackathon drop day so queries `as_of_date` never leak
future information into earlier days.
"""

from __future__ import annotations

from datetime import date

RELEASE_DATES: dict[str, str] = {
    "Day1_Mon_16Nov": "2026-11-16",
    "Day2_Tue_17Nov": "2026-11-17",
    "Day3_Wed_18Nov": "2026-11-18",
    "Day4_Thu_19Nov": "2026-11-19",
}

DAY1_FILES: set[str] = {
    "Candidate_Brief.docx",
    "README.txt",
    "Board_Update_Apr-Jun_2026.pdf",
    "Board_Update_Jul-Sep_2026.pdf",
    "GL_Export_Apr-Sep_2026.xlsx",
    "Payroll_Register_Jan-Mar_2026.xlsx",
    "Employee_Master.xlsx",
    "Connection_Worksheet.pdf",
    "Entity_Resolution.xlsx",
    "Evidence_Index.xlsx",
    "01.eml",
    "02.eml",
    "03.eml",
    "T1_CEO_Kickoff_Call.docx",
    "T2_CFO_Call.docx",
}

DAY2_FILES: set[str] = {
    "Hiring_Tracker.xlsx",
    "Leave_Register.xlsx",
    "Pulse_Survey.xlsx",
    "Resignation_Letter_SM.pdf",
    "06.eml",
    "07.eml",
    "10.eml",
    "11.eml",
    "T3_Head_of_People_Call.docx",
    "T6a_CEO_Voice_Note.docx",
}

DAY3_FILES: set[str] = {
    "Jira_Export_ATLAS.xlsx",
    "git_log.csv",
    "Incidents_Aug-Oct_2026.xlsx",
    "OnCall_Rota.xlsx",
    "Atlas_Launch_Kit_v1.pdf",
    "Invoice_PIS-114.pdf",
    "Email_Printouts.pdf",
    "04.eml",
    "05.eml",
    "08.eml",
    "09.eml",
    "T4_Head_of_Marketing_Call.docx",
    "T5_VP_Engineering_Call.docx",
    "T6b_CEO_Voice_Note.docx",
}


def validate_iso_date(value: str) -> str:
    """Validate YYYY-MM-DD format and return normalized string."""
    parsed = date.fromisoformat(value.strip())
    return parsed.isoformat()


def release_date_for_folder(folder_name: str) -> str:
    """Return official release_date (YYYY-MM-DD) for a release pack folder."""
    if folder_name in RELEASE_DATES:
        return RELEASE_DATES[folder_name]
    raise ValueError(f"Unknown release pack folder: {folder_name}")


def is_visible_as_of(record_release_date: str, as_of_date: str) -> bool:
    """Return True iff record was released on or before `as_of_date`."""
    return validate_iso_date(record_release_date) <= validate_iso_date(as_of_date)
