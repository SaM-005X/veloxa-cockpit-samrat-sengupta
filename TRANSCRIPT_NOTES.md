# Transcript Notes — Mishearings & Contradictions

> Tracks suspected ASR/transcription mishearings and cross-source contradictions across leadership calls, together with the corroborating evidence and my own conclusion.

---

## Day 1 (`2026-11-16`) — `T1_CEO_Kickoff_Call.docx` & `T2_CFO_Call.docx`

### 1. Suspected Mishearings (ASR / Transcription Errors)

| Transcript | Transcript Text | Likely Intended Term | Evidence Used | My Conclusion |
| :--- | :--- | :--- | :--- | :--- |
| `T1` | `"eighteen people ('one-eighty')"` | **19 employees** (or speaker said 18/19, transcriber parenthetically guessed `"one-eighty"` from brief) | `Employee_Master.xlsx` (19 employee rows); `Candidate_Brief.docx` ("180-person" typo) | Veloxa has **19 employees**. Both `"one-eighty"` and `"eighteen"` are inaccurate; use `Employee_Master.xlsx` as ground truth. |
| `T1` / `T2` | `"Joho books"` | **Zoho Books** | `T2_CFO_Call.docx` (Tally -> Zoho Books migration in Jan/Feb); `GL_Export_Apr-Sep_2026.xlsx` | Standard ASR phonetic error for Zoho Books. Map `"Joho books"` -> `Zoho Books` in `entity_aliases`. |
| `T1` / `T2` | `"Kayka"` / `"Kekka"` | **Keka** (HRMS / Payroll) | `Employee_Master.xlsx` / HR tooling references | Map `"Kayka"` / `"Kekka"` -> `Keka`. |
| `T1` | `"Jeera"` | **Jira** | Engineering issue tracker context | Map `"Jeera"` -> `Jira`. |
| `T1` / `T2` | `"Kartik"` / `"Fatima Shaikh"` / `"Pria"` / `"Vicky"` | **Karthik Subramanian** (`VX010`), **Fatima Sheikh** (`VX014`), **Priya Nair** (`VX007`), **Vikram Menon** (`VX004`) | `Employee_Master.xlsx`; `01.eml`–`03.eml` | Normalize all phonetic spelling variants and nicknames to canonical `VX*` IDs in `entity_aliases`. |
| `T1` | `"slag"` / `"hub sport"` / `"Con fluence"` | **Slack**, **HubSpot**, **Confluence** | General SaaS stack references in `T1` | Map to canonical tool names, and explicitly record that no Slack/HubSpot/Confluence exports exist in the Day 1 data room. |

---

### 2. Contradictions & Discrepancies (Day 1 Scope)

| ID | Topic | Verbal / Brief Claim | Corroborated Record Evidence | My Conclusion |
| :--- | :--- | :--- | :--- | :--- |
| **C01** | **Company Size, ARR & Burn** | `Candidate_Brief.docx` says `"180-person"`; `T1` cites ARR `"forty-two crore, maybe forty-five"` and monthly burn `"two point two"`. | `Employee_Master.xlsx` lists **19 employees**. `Board_Update_Apr-Jun_2026.pdf` and `Board_Update_Jul-Sep_2026.pdf` report **ARR Rs. 5.8 Cr (Q1) -> Rs. 6.1 Cr (Q2)**, **monthly burn Rs. 46 L (Q1) -> Rs. 44 L (Q2)**, and **runway 14 -> 13 months**. | The CEO kickoff call figures appear roughly 7–10x inflated (or misheard/misremembered). Trust `Employee_Master.xlsx` and the two `Board_Update` PDFs as primary financial truth, while flagging the discrepancy transparently. |
| **C02** | **February Payroll Proration** | `Payroll_Register_Jan-Mar_2026.xlsx` shows Rahul Verma (`VX018`) paid `28/28` days (full Rs. 1,10,000 gross) in Feb 2026, and March shows no adjustment. | `Employee_Master.xlsx` shows Rahul joined **`2026-02-03`** (`26/28` eligible days). `01.eml`–`03.eml` show Fatima (`FS`) was on leave Feb 9–27, Karthik (`KS`) ran Feb payroll, Rahul flagged the error (`02.eml`), and Fatima replied `"Will check and get back"` (`03.eml`). | Confirmed unresolved payroll over-payment bug in Feb 2026. Cockpit will flag this as an open finance/payroll control item without exposing individual salary figures in Q&A. |
| **C03** | **Atlas v3 Launch Timing** | `Board_Update_Apr-Jun_2026.pdf` planned GA for `2026-09-15`. | `Board_Update_Jul-Sep_2026.pdf` states Atlas v3 is in `"final hardening"` and GA moved without a specific new date; `T1` expresses doubt on making the festive season. | As of Day 1 (`2026-11-16`), Atlas v3 has missed its Sep 15 target and has **no confirmed GA date** in the data room. Await Day 2/3 Engineering & Product drops rather than guessing a date. |
