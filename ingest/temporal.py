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
