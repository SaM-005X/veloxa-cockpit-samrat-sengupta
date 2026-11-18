# Voice Note Response: T6b (Marketing Reporting Reorg & Org Flexibility)

**Date:** Wednesday, 18 November 2026  
**From:** CXO Cockpit Engineering & Strategy Team  
**To:** Ananya Rao, CEO, Veloxa Technologies  
**Voice Note ID:** `T6b`  
**Decision Status:** **Partial Implementation + Reasoned Pushback (`partial`)**

---

## 1. CEO Voice Note Request

> *"So, marketing will report to the new CRO from next month. Or the month after, still finalising. Make sure the thing doesn't break when we move people around."*  
> — **Ananya Rao, CEO** (`T6b_CEO_Voice_Note.docx`)

---

## 2. What We Implemented (Technical Resilience: Zero Breakage on Reorg)

To guarantee the Cockpit never breaks when reporting lines or departments change:

1. **Temporal `reporting_lines` Architecture (`db/schema.sql` & `db/database.py`):**
   - Reporting relationships (`employee_id`, `manager_id`, `department`, `effective_from`, `effective_to`, `source_ref`, `release_date`) are decoupled from the static `employees` directory.
   - Added `get_reporting_line_as_of(employee_id, as_of_date)` so historical Time Machine views (`2026-11-16`, `2026-11-17`, `2026-11-18`) continue resolving Nikhil Bose (`VX006`) and Aisha Khan (`VX011`) under their historical reporting lines without mutating past records or breaking joins across `payroll_summary`, `gl_transactions`, `pulse_surveys`, or the 14 AI agent personas.
2. **Department-Agnostic Cost Center & Survey Joins:**
   - Financial spend (`MKT-PS`, `MKT-EVT` in `gl_transactions`) and Culture Amp team scores (`pulse_surveys`) remain anchored by stable cost-center codes and survey periods rather than hard-coded manager IDs.

---

## 3. Reasoned Pushback: Do Not Execute Live Marketing Reorg Yet

While the **database and Cockpit are fully ready** for a future CRO reporting transition, **we push back against changing Marketing's live reporting line today (`2026-11-18`)** for four evidence-backed reasons from Day 1–3 records:

1. **No CRO Exists in HRMS or Hiring Requisitions:**
   - `Employee_Master.xlsx` (`E001`) lists 19 FTEs (`VX001`–`VX019`) with no CRO on payroll.
   - `Hiring_Tracker.xlsx` (`E022`) lists 6 requisitions (`REQ-011`, `REQ-013`–`REQ-017`) and **zero open CRO requisitions**. In fact, the only Sales req (`REQ-011`, Account Executive) was closed not hired on `2026-04-02` with its budget moved to Marketing (`E025`), and `T6b` itself notes the timeline is still unfinalized (*"next month. Or the month after, still finalising"*).
2. **Unresolved Rs. 3,73,380 Marketing Spend Discrepancy (`C12`):**
   - In `T4_Head_of_Marketing_Call.docx` (`E049`), Head of Marketing Nikhil Bose (`VX006`) claims half-year Marketing spend is `"one point eight"` (Rs. 18,00,000), whereas Zoho Books `GL_Export_Apr-Sep_2026.xlsx` (`E018`) books **Rs. 14,26,620** (`MKT-PS` Google Ads Rs. 4,23,620 + `MKT-EVT` Summit Rs. 10,03,000).
   - Moving Marketing under a new executive before Performance Marketing Manager Aisha Khan (`VX011`) completes her `T4` action item (*"Send the campaign sheet to finance"*) risks losing accountability for the Rs. 3.73 L variance.
3. **Marketing Morale Dip, PMM Vacancy & Cold Summit Leads (`C12`, `C13`):**
   - Product Marketing Manager Siddharth Mehta (`VX013`) exited on `2026-10-31` (`Resignation_Letter_SM.pdf`, `E031`), leaving his completed `Atlas_Launch_Kit_v1.pdf` (`E045`) unpublished and backfill `REQ-016` (7 candidates) still open (`E024`).
   - Marketing Culture Amp engagement fell to **3.4** (`Pulse_Survey.xlsx`, `E030`), and Sales Lead Manoj Kumar (`VX002`) flagged that the September summit leads are *"cold"* (`T4`, `E050`)—a sales-marketing handoff friction that will worsen if leadership shifts without clear lead-qualification SLAs.
4. **Data Room Blind Spots (`HubSpot` & `LinkedIn Campaign Manager`):**
   - Neither HubSpot CRM deal conversion data nor LinkedIn Campaign Manager exports exist in the data room (`T4`), making it impossible to evaluate Marketing-to-Sales funnel ROI before a CRO takeover.

---

## 4. Concrete Next Steps Proposed

| Step | Owner | Action | Gate Before Moving Reporting Line |
| :--- | :--- | :--- | :--- |
| **1** | CEO (`VX001`) & People (`VX005`) | Confirm CRO offer, entity ID, and exact start date in Keka (`Employee_Master`). | Insert `reporting_lines` row with `effective_from = <CRO Start Date>` only once confirmed. |
| **2** | Aisha (`VX011`) & Meera (`VX003`) | Reconcile Marketing campaign sheet (including any unbooked Sep/Oct LinkedIn/Google Ads) against Zoho Books GL (`Rs. 14,26,620`). | Close the Rs. 3.73 L variance (`C12`) prior to handover. |
| **3** | Rohan (`VX015`) & Nikhil (`VX006`) | Close `REQ-016` (PMM backfill, 7 candidates in pipeline) and hand off `Atlas_Launch_Kit_v1.pdf` against Jira's revised `2026-12-15` GA target. | Stabilize Marketing headcount (currently down to 2 active FTEs). |
| **4** | Nikhil (`VX006`) & Manoj (`VX002`) | Define MQL/SQL acceptance criteria for the 212 September summit registrations before merging Marketing under Revenue/CRO. | Prevent ongoing "cold lead" blame-shifting post-reorg. |

*Submitted by CXO Cockpit Architecture Team — 18 Nov 2026*
