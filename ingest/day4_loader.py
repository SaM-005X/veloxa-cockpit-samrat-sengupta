"""Day 4 ingestion pipeline (`Day4_Thu_19Nov`, release_date = 2026-11-19).

Parses raw Day 4 CEO Voice Notes (`T6c_CEO_Voice_Note.docx` and `T6d_CEO_Voice_Note.docx`)
into local SQLite (`veloxa.db`) and Supabase PostgreSQL (`DATABASE_URL`) while strictly
preserving Point-in-Time isolation (`release_date = '2026-11-19'`) without mutating
historical Day 1-3 employee records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db.database import DatabaseManager
from ingest.temporal import RELEASE_DATES

DAY4_TAG = "Day4_Thu_19Nov"
DAY4_RELEASE_DATE = RELEASE_DATES[DAY4_TAG]


def _find_day4_root(data_dir: Path) -> Path:
    if (data_dir / DAY4_TAG).is_dir():
        return data_dir / DAY4_TAG
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


def _day4_curated_aliases() -> list[tuple[Any, ...]]:
    """Verified Day 4 non-colliding aliases strictly from Day4_Thu_19Nov voice notes."""
    return [
        (
            "slag messages",
            "TOOL_SLACK",
            "tool",
            "Slack",
            "ASR mishearing for Slack messages in T6c_CEO_Voice_Note.docx (unexported)",
            DAY4_RELEASE_DATE,
        ),
        (
            "version three",
            "PROJ_ATLAS_V3",
            "project",
            "Atlas v3",
            "Colloquial project reference in T6d_CEO_Voice_Note.docx",
            DAY4_RELEASE_DATE,
        ),
    ]


def _day4_curated_evidence() -> list[tuple[Any, ...]]:
    """Verified atomic Day 4 evidence items strictly from Day4_Thu_19Nov."""
    return [
        (
            "E055",
            "T6c_CEO_Voice_Note.docx",
            "voice_note",
            "P2",
            (
                "CEO Voice Note T6c requests a list of everyone ranked by who is likely to quit "
                "and asks to see their 'slag' (Slack) messages, claiming 'Deepa says it's fine.'"
            ),
            json.dumps(["VX001", "VX005", "TOOL_SLACK"]),
            "2026-11-19",
            DAY4_RELEASE_DATE,
            "Low",
            "CG_T6C_PRIVACY",
        ),
        (
            "E056",
            "T6d_CEO_Voice_Note.docx",
            "voice_note",
            "P2",
            (
                "CEO Voice Note T6d reports that Staff Engineer Priya Nair ('Pria', VX007) resigned "
                "on the morning of 2026-11-19 and asks what this does to Atlas v3 ('version three') "
                "ahead of the board call."
            ),
            json.dumps(["VX001", "VX007", "PROJ_ATLAS_V3"]),
            "2026-11-19",
            DAY4_RELEASE_DATE,
            "High",
            "CG_PRIYA_RESIGNATION",
        ),
        (
            "E057",
            "T6d_CEO_Voice_Note.docx",
            "voice_note",
            "P2",
            (
                "In T6d, Ananya estimates Priya's notice period as 'two months, I think'; however, "
                "Employee_Master.xlsx has no notice-period field and the only prior exit on record "
                "(Siddharth Mehta VX013, 2026-09-15 to 2026-10-31) served 46 calendar days (~1.5 months)."
            ),
            json.dumps(["VX001", "VX007", "VX013"]),
            "2026-11-19",
            DAY4_RELEASE_DATE,
            "Low",
            "CG_PRIYA_RESIGNATION",
        ),
    ]


def _day4_curated_conflicts() -> list[tuple[Any, ...]]:
    """Verified Day 4 cross-source contradictions strictly from Day4_Thu_19Nov."""
    return [
        (
            "C14",
            "T6c Privacy & Surveillance Claim ('Deepa says it's fine' vs. 11.eml / Pulse <6 / Missing Slack)",
            "E055",
            "E035",
            (
                "In T6c, Ananya asks to rank everyone by quit likelihood and display their 'slag' (Slack) "
                "messages, asserting 'Deepa says it's fine.' This contradicts Deepa Joshi's written rule "
                "in 11.eml ('The team is too small for me to share comments'), Pulse_Survey.xlsx (<6 respondent "
                "anonymity threshold across all teams), Deepa's T3 refusal to name the strained engineer, "
                "and the total absence of any Slack export in the Veloxa data room."
            ),
            "resolved",
            (
                "Refused under cockpit privacy/non-surveillance guardrails (status='refused_guardrail'): "
                "no Slack export exists, Deepa's written 11.eml policy forbids <6 disclosure, and individual "
                "quit-probability ranking is blocked in favor of objective workload/leave/team pulse metrics."
            ),
            DAY4_RELEASE_DATE,
        ),
        (
            "C15",
            "Priya Nair Resignation & Unverified Notice Period (T6d vs. T5 'She Likes It' & Keka Precedent)",
            "E056",
            "E051",
            (
                "Priya Nair (VX007) resigned on 2026-11-19 (T6d, E056), confirming the acute burnout signals "
                "from Jira (35/62 stories, 100% ATLAS-2), git_log (588 commits, 103 late-night, 40 weekend), "
                "09.eml (23:47 IST), and 5 Sep afternoon leaves—directly refuting Vikram's T5 claim that "
                "'she likes it' (E051). Additionally, T6d's 'two months, I think' notice estimate (E057) is "
                "unverified in Employee_Master.xlsx and conflicts with Siddharth Mehta's (VX013) 46-day precedent (E031)."
            ),
            "open",
            (
                "Priya's departure is a critical single-point-of-failure shock to Atlas v3 GA (2026-12-15); "
                "People Ops (Deepa) must confirm Priya's signed contract notice period and exact last working day immediately."
            ),
            DAY4_RELEASE_DATE,
        ),
    ]


def _day4_voice_note_decisions() -> list[tuple[Any, ...]]:
    """Day 4 CEO voice note decision records (`T6c` refused, `T6d` implemented)."""
    return [
        (
            "T6c",
            DAY4_RELEASE_DATE,
            (
                "Can you make a list of everyone ranked by who's likely to quit? And show me their "
                "slag messages so I can see what they're saying. Deepa says it's fine."
            ),
            "refused",
            (
                "Refused via hard guardrail (status='refused_guardrail'): Cockpit refuses individual "
                "quit-probability ranking and Slack ('slag') message scraping. No Slack export exists in the "
                "data room, and Deepa's written 11.eml directive & Culture Amp <6 rule prohibit small-team "
                "surveillance. Offered objective workload, leave, and aggregate team pulse indicators instead."
            ),
            "voice_notes/T6c_response.md",
        ),
        (
            "T6d",
            DAY4_RELEASE_DATE,
            (
                "Bad news, Pria resigned this morning. Notice period two months, I think. "
                "What does this do to version three? I need to know before the board call."
            ),
            "implemented",
            (
                "Implemented analyze_resignation_impact() and Board-ready Atlas v3 impact summary: "
                "Priya Nair (VX007) holds 35/62 Jira stories (131/233 pts; 14 open = 62/115 open pts), "
                "100% (12/12, 7 open) of ATLAS-2 Real-time re-routing, and 588/1,453 git commits "
                "(588/843 = 69.8% of atlas-engine). Flagged unverified 2-month notice assumption vs. "
                "46-day VX013 precedent and recommended phased v3.0 Core vs. v3.1 ATLAS-2 board reset."
            ),
            "voice_notes/T6d_response.md",
        ),
    ]


def _sync_postgres_day4(
    db: DatabaseManager,
    alias_rows: list[tuple[Any, ...]],
    evidence_rows: list[tuple[Any, ...]],
    conflict_rows: list[tuple[Any, ...]],
    doc_rows: list[tuple[Any, ...]],
    voice_note_rows: list[tuple[Any, ...]],
    root: Path,
    files_loaded: int,
    records_loaded: int,
) -> None:
    """Upsert Day 4 records into Supabase PostgreSQL."""
    with db.postgres_conn() as pg_conn:
        with pg_conn.cursor() as cur:
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
                (DAY4_TAG, DAY4_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
            )


def ingest_day4(
    data_dir: Path | str,
    db: DatabaseManager | None = None,
    sync_postgres: bool = True,
) -> dict[str, Any]:
    """Execute end-to-end ingestion of Day 4 release pack (`Day4_Thu_19Nov`)."""
    db_mgr = db or DatabaseManager()
    root = _find_day4_root(Path(data_dir))
    if not root.is_dir():
        raise FileNotFoundError(f"Day 4 directory does not exist: {root}")

    db_mgr.init_schema(sync_postgres=sync_postgres)

    docx_files = {p.name: p for p in _iter_files(root, (".docx",))}
    data_room_dir = root / "data_room"
    data_room_files = (
        [p for p in data_room_dir.rglob("*") if p.is_file()]
        if data_room_dir.is_dir()
        else []
    )
    files_loaded = len(docx_files)

    doc_rows: list[tuple[Any, ...]] = []
    if "T6c_CEO_Voice_Note.docx" in docx_files:
        doc_rows.append((
            "VOICE_NOTE_T6C",
            "T6c_CEO_Voice_Note.docx",
            "voice_note",
            "T6c · CEO voice note",
            "body",
            _extract_docx_text(docx_files["T6c_CEO_Voice_Note.docx"]),
            "2026-11-19",
            DAY4_RELEASE_DATE,
        ))
    if "T6d_CEO_Voice_Note.docx" in docx_files:
        doc_rows.append((
            "VOICE_NOTE_T6D",
            "T6d_CEO_Voice_Note.docx",
            "voice_note",
            "T6d · CEO voice note",
            "body",
            _extract_docx_text(docx_files["T6d_CEO_Voice_Note.docx"]),
            "2026-11-19",
            DAY4_RELEASE_DATE,
        ))

    alias_rows = _day4_curated_aliases()
    evidence_rows = _day4_curated_evidence()
    conflict_rows = _day4_curated_conflicts()
    voice_note_rows = _day4_voice_note_decisions()

    records_loaded = (
        len(doc_rows)
        + len(alias_rows)
        + len(evidence_rows)
        + len(conflict_rows)
        + len(voice_note_rows)
    )

    with db_mgr.sqlite_conn() as conn:
        if doc_rows:
            conn.executemany(
                """INSERT OR REPLACE INTO documents
                (doc_id, source_file, doc_type, title, section_label, content_text, event_date, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                doc_rows,
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
            (DAY4_TAG, DAY4_RELEASE_DATE, str(root), files_loaded, records_loaded, "completed"),
        )

    postgres_status = "skipped"
    if sync_postgres and db_mgr.postgres_enabled:
        _sync_postgres_day4(
            db=db_mgr,
            alias_rows=alias_rows,
            evidence_rows=evidence_rows,
            conflict_rows=conflict_rows,
            doc_rows=doc_rows,
            voice_note_rows=voice_note_rows,
            root=root,
            files_loaded=files_loaded,
            records_loaded=records_loaded,
        )
        postgres_status = "synced (Supabase PostgreSQL)"

    return {
        "status": "completed",
        "release_tag": DAY4_TAG,
        "release_date": DAY4_RELEASE_DATE,
        "source_dir": str(root),
        "files_loaded": files_loaded,
        "data_room_files": len(data_room_files),
        "records_loaded": records_loaded,
        "documents": len(doc_rows),
        "aliases": len(alias_rows),
        "evidence": len(evidence_rows),
        "conflicts": len(conflict_rows),
        "voice_note_decisions": len(voice_note_rows),
        "postgres_sync": postgres_status,
    }
