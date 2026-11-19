# Voice Note Response: T6d (Priya Nair Resignation — Board Atlas v3 Impact Analysis)

**Date:** Thursday, 19 November 2026  
**From:** CXO Cockpit Engineering & Strategy Team  
**To:** Ananya Rao, CEO, Veloxa Technologies  
**Voice Note ID:** `T6d`  
**Decision Status:** **Implemented (`analyze_resignation_impact()` + Board Reset Plan)**

---

## 1. CEO Voice Note Request

> *"Bad news, Pria resigned this morning. Notice period two months, I think. What does this do to version three? I need to know before the board call."*  
> — **Ananya Rao, CEO** (`T6d_CEO_Voice_Note.docx`, P2 `[E056]`, `[E057]`)

---

## 2. Executive Board Verdict (Bottom Line Up Front)

**Priya Nair (`VX007`, `"Pria"`, Staff Engineer) is the single highest-concentration contributor on Atlas v3 (`"version three"`).** Her resignation on **19 Nov 2026**—just **26 calendar days** before Vikram Menon's Jira GA target of **15 Dec 2026** (`[E036]`)—makes **shipping full-scope Atlas v3 on `2026-12-15` unachievable without immediate scope reduction or a retained/backfilled handover plan**.

Specifically, **Epic `ATLAS-2` (*Real-time re-routing*) is a 100% single point of failure (`12/12` stories, `7` still open)**, and **`atlas-engine` loses 69.8% of its historical commit authorship** (`588/843` commits) with **zero active backend engineering requisitions open** (`REQ-014` and `REQ-015` have been frozen since `2026-08-12` `[E023]`).

---

## 3. Quantified Impact on Atlas v3 (`release_date <= 2026-11-19`)

Computed dynamically via `cockpit.risk_engine.analyze_resignation_impact(db, "VX007", "2026-11-19")`:

### A. Jira Exposure (`Jira_Export_ATLAS.xlsx` `[E036]`, `[E037]`, `[E038]`, `[E039]`)

| Metric | Priya Nair (`VX007` / `PN`) | Entire Atlas v3 Project | Priya's Share | Board Risk |
| :--- | :---: | :---: | :---: | :--- |
| **Total Stories Assigned** | **35** | 62 | **56.5%** | Over half of all Atlas v3 stories sit with one departing engineer. |
| **Total Story Points** | **131** | 233 | **56.2%** | Exceeds the combined load of Arjun, Rahul, Sneha, and Vikram. |
| **Done Stories / Points** | 21 stories (69 pts) | 35 stories (118 pts) | 60.0% of Done | Historical domain knowledge of completed routing core leaves with her. |
| **Open Stories (`In Progress` + `To Do`)** | **14** (7 IP + 7 To Do) | 27 (8 IP + 19 To Do) | **51.9%** | **More than half of remaining ticket count** belongs to Priya. |
| **Open Story Points** | **62** (36 IP + 26 To Do) | 115 (38 IP + 77 To Do) | **53.9%** | **36 of 38 `In Progress` points (94.7%)** are actively mid-flight under Priya. |

#### Epic-by-Epic Exposure Breakdown

| Epic | Epic Name | Priya / Total Stories | Ownership % | Priya Open Stories (Pts) | Other Engineers' Ownership & Status |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`ATLAS-1`** | Core routing engine v3 | **13 / 16** | **81.3%** | **3 open (14 pts)**: `ATLAS-19` (8pt IP), `ATLAS-21` (3pt IP), `ATLAS-16` (3pt To Do) | Rahul (`VX018`) holds 3 stories (1 Done, 2 To Do = 6 pts). |
| **`ATLAS-2`** | **Real-time re-routing** | **12 / 12** | **100.0% SPOF** | **7 open (29 pts — 69.0% of epic pts!)**: `ATLAS-29` (8pt IP), `ATLAS-38` (3pt IP), `ATLAS-27` (2pt To Do), `ATLAS-30` (3pt To Do), `ATLAS-32` (5pt To Do), `ATLAS-35` (3pt To Do), `ATLAS-36` (5pt To Do) | **ZERO other engineers hold any `ATLAS-2` ticket.** |
| **`ATLAS-3`** | Public API v3 | 4 / 12 | 33.3% | 0 open (all 4 Done, 19 pts) | Rahul (`VX018`) owns remaining 8 stories (3 Done, 1 IP, 4 To Do = 19 open pts). |
| **`ATLAS-4`** | Planner UI | 0 / 12 | 0.0% | 0 | Arjun (`VX009`) owns 12/12 (10 Done, 2 To Do = 10 open pts). |
| **`ATLAS-5`** | Performance & hardening | **6 / 10** | **60.0%** | **4 open (19 pts)**: `ATLAS-68` (3pt IP), `ATLAS-70` (8pt IP), `ATLAS-72` (3pt IP), `ATLAS-67` (5pt To Do) | Sneha (`VX012`) holds the other 4 (all To Do, 18 pts)—**paused** due to `routing-api` SEV1s (`08.eml` `[E047]`). Thus **8/10 `ATLAS-5` stories (37/43 pts = 86.0%) are unfinished**. |

### B. Codebase & Operational Signals (`git_log.csv`, `Leave_Register.xlsx`, `OnCall_Rota.xlsx`, `Hiring_Tracker.xlsx`)

- **Git Codebase Concentration (`[E040]`, `[E041]`):** Priya authored **588 / 1,453 company commits (40.5%)** across two Git identities (`priya.n@veloxa.in`: 425; `pnair@users.noreply.github.com`: 163). All 588 commits are in **`atlas-engine`**, where she wrote **588 / 843 commits (69.8%)**—nearly 5x more than Rahul Verma (`VX018`: 117 commits, `13.9%`) or Sneha Kulkarni (`VX012`: 115 commits, `13.6%`), while VP Eng Vikram Menon (`VX004`) authored only 23 (`2.7%`).
- **Unsustainable Heroics Masked Until Exit (`[E040]`, `[E048]`, `[E051]`, `C10`/`C15`):** Starting June 2026, Priya logged **103 late-night commits (22:00–05:59 IST)** and **40 weekend commits** (**100%** of Veloxa's after-hours commits; every other engineer has **0**). She emailed Vikram at **23:47 IST on 01-Sep** asking to discuss Atlas ownership (`09.eml` `[E048]`)—one day before Vikram quietly pushed GA to `2026-12-15` (`[E036]`)—and took **5 half-day PM leaves in September** (`2026-09-03`, `08`, `15`, `17`, `24` `[E026]`).
- **On-Call & Production Risk (`[E042]`, `[E043]`):** While Priya had 0 Primary on-call weeks, she served **3 Secondary weeks** and `routing-api` already suffered **3 SEV1 outages in August** handled by Sneha (`VX012`). Losing `atlas-engine`'s primary architect right before GA elevates post-launch incident risk sharply.
- **Zero Ready Backend Backfill (`[E017]`, `[E023]`, `[E032]`):** Requisitions `REQ-014` (Senior Backend — Routing, 3 candidates) and `REQ-015` (Senior Backend — Platform, 5 candidates) were frozen on `2026-08-12`, stranding **8 candidates** and an idle **Rs. 1,77,000** recruiting advance to Cohere (`JV-0688`).

---

## 4. Pushback on Unrealistic Assumptions in `T6d`

Before presenting to the Board, leadership must correct **three unrealistic assumptions** embedded in `T6d`:

1. **Pushback #1 — `"Notice period two months, I think"` Is Unverified and Contradicted by Precedent (`[E057]`, `C15`):**
   - `Employee_Master.xlsx` (`[E001]`) contains **no notice-period column**, and no employment contract is in the data room.
   - The only documented resignation at Veloxa—Siddharth Mehta (`VX013`, `Resignation_Letter_SM.pdf` `[E031]`)—was submitted `2026-09-15` with last working day `2026-10-31`, which is **46 calendar days (~1.5 months)**, **not 60 days**.
   - **Impact:** If Priya's notice is 45–46 days (or shortened via buyout), her last working day lands around **03–04 Jan 2027** (or earlier), **leaving almost zero overlap after `2026-12-15` GA** unless handover starts immediately. Even at 60 days (~`2027-01-18`), she cannot be treated as full-capacity execution bandwidth.
2. **Pushback #2 — Notice-Period Velocity Cannot Match Prior Burnout Heroics:**
   - Priya's historical pace relied on **103 late-night** and **40 weekend** commits (`[E040]`). During notice, at least **40–50%** of her hours must shift from net-new coding to documentation, code walkthroughs, and pair debugging with Rahul (`VX018`) and Sneha (`VX012`). Assuming she can finish **14 open stories (62 pts)** *and* transfer ownership of `588` commits in 26 days before `2026-12-15` is unrealistic.
3. **Pushback #3 — Keeping Full-Scope `2026-12-15` GA Creates a Post-GA Support Cliff:**
   - Even if code were rushed to `2026-12-15`, shipping `ATLAS-2` (*Real-time re-routing*) with **0% secondary engineer familiarity** right as Priya exits creates severe January production outage risk on top of `routing-api`'s August SEV1 history (`[E042]`).

---

## 5. Board-Ready Recommendation & Concrete Mitigation Plan

### Recommended Board Framing: Split Atlas v3 Into Two Controlled Releases
- **Atlas v3.0 Core (Target late Dec 2026 / early Jan 2027):** Complete remaining `ATLAS-1` (3 Priya + 2 Rahul stories), `ATLAS-3` API (5 Rahul open stories), `ATLAS-4` UI (2 Arjun open stories), and critical `ATLAS-5` hardening/canary/chaos items.
- **Atlas v3.1 Fast-Follow (Q4 FY27 / Jan–Feb 2027):** Defer **`ATLAS-2` Real-time re-routing** (7 open stories / 29 pts) to v3.1 unless a structured retention bridge or rapid senior backfill secures safe dual-ownership.

### Immediate Action Plan

| Horizon | Owner | Concrete Action | Evidence / Constraint |
| :--- | :--- | :--- | :--- |
| **Today (Next 4 hrs)** | **Deepa Joshi (`VX005`)** & **Ananya (`VX001`)** | Verify Priya's exact signed notice period & last working day (`46d` vs `60d`); hold a candid exit/retention conversation (`11.eml` `[E035]`). | Resolve `E057` / `C15` before the board call. |
| **Within 48 Hours** | **Vikram Menon (`VX004`)** | Freeze all non-core scope; re-assign `ATLAS-1` remaining 3 open stories (`ATLAS-19/21/16`) and `ATLAS-5` (`ATLAS-67/68/70/72`) into daily pair-programming between **Priya (`VX007`)**, **Rahul (`VX018`, 117 `atlas-engine` commits)**, and **Sneha (`VX012`, 115 `atlas-engine` commits)**. | `[E038]`, `[E039]`, `[E041]`. |
| **Week 1 (`Nov 20–27`)** | **Meera Iyer (`VX003`)** & **Rohan (`VX015`)** | Unfreeze `REQ-014` and `REQ-015` immediately; re-contact the **8 previously vetted backend candidates** and deploy the idle **Rs. 1,77,000 Cohere Recruiting advance (`JV-0688`)** toward a Staff/Senior Routing backfill. | `[E017]`, `[E023]`, `[E032]`. |
| **Weeks 1–3 (`Nov 20–Dec 11`)** | **Priya (`VX007`)** & **Sneha (`VX012`)** | Lock Priya's final deliverables to: (a) clean merge/documentation of `In Progress` work (`ATLAS-19`, `21`, `29`, `38`, `68`, `70`, `72`), (b) architecture runbooks for `atlas-engine` & `ATLAS-2`, and (c) unblocking Sneha's 4 paused `ATLAS-5` perf tickets (`[E047]`). | Protects production reliability & Runway (`13 months`, Rs. 44–46L burn `[E005]`). |

*Prepared by CXO Cockpit Strategy & Engineering Intelligence Team — 19 Nov 2026*
