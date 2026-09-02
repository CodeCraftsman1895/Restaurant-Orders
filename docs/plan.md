# Plan

## How did you break the work into sessions?

The project was divided into five distinct working sessions comprising 12 sequential phases:

* **Session 1 (Phases 1–3) — Data Architecture & Hosting Foundation:**
  * Analyzed assignment requirements and designed the 7-table schema with 17 indexes (`docs/schema.md`).
  * Built SQLAlchemy 2.0 ORM models and generated the Alembic migration script.
  * Connected to hosted Supabase PostgreSQL over SSL and executed an idempotent seed script providing 4 users, 15 dishes, 12 core orders, and 35+ historical records.

* **Session 2 (Phases 4–5) — Security, Authentication & Role-Based Access Control:**
  * Implemented bcrypt password hashing and HS256 JWT access token issuance (`POST /api/auth/login`, `GET /api/auth/me`).
  * Enforced server-side role dependencies (`require_manager`, `require_waiter_or_manager`) and order-level ownership rules.

* **Session 3 (Phases 6–7) — Core Business Operations & Order Lifecycle:**
  * Implemented menu management: CRUD, availability toggling, archiving, and Goal 7 bulk updates with itemized per-item results.
  * Implemented the full order lifecycle state machine (*Placed → Accepted → Preparing → Ready → Served*), cancellation safeguards, line voiding with required reasons, multi-waiter collaboration, and append-only audit event logging.

* **Session 4 (Phases 8–9) — Monitoring, Analytics & Data Export:**
  * Built Goal 10 slow-order alert engine with 15-minute threshold detection, navbar badge polling, and 10-minute acknowledgment suppression/reappearance.
  * Implemented Goal 8 Manager Dashboard (headline KPIs, today's served revenue, continuous 14-day history) and streaming CSV export.

* **Session 5 (Phases 10–12) — User Interface, Integration Verification & Deployment:**
  * Built the responsive Vanilla HTML5/CSS3/JavaScript frontend with Chart.js integration across 7 views.
  * Mounted static files in FastAPI, created an automated integration suite (54/54 tests passing), and configured Render production hosting.

---

## What order did you build in, and why that order?

We followed a strict **dependency-first, bottom-up order**:

```
Database Schema (PostgreSQL/Supabase)
          ↓
ORM Models & Migrations (SQLAlchemy/Alembic)
          ↓
Authentication & Authorization (JWT/RBAC)
          ↓
Domain Services & REST APIs (FastAPI)
          ↓
Frontend Web Interface (HTML5/CSS3/JS/Chart.js)
          ↓
Full Integration Verification (pytest)
          ↓
Cloud Hosting Deployment (Render)
```

**Why this order?**
1. **Data Integrity First:** In a restaurant system with price snapshots and audit timelines, any flaw in the data model ripples upward into APIs and UI. Establishing the relational schema and migrations first guaranteed stable ground.
2. **Security Before Business Logic:** Implementing JWT and role-based access control early ensured every subsequent business endpoint was secured from inception, rather than bolting security on retroactively.
3. **API Contracts Before UI:** Defining and verifying REST endpoints with automated tests provided reliable API contracts for frontend integration.
4. **UI and Verification:** With functional endpoints, building the frontend was straightforward fetch integration.
5. **Deployment:** Configuring PaaS hosting once the local container and test suite were 100% green eliminated debugging in cloud environments.

---

## What did you estimate versus what it actually took?

We budgeted approximately **12 hours** total. The actual time spent was approximately **11.5 hours**:

| Phase / Area | Estimated Time | Actual Time | Variance & Notes |
|---|:---:|:---:|---|
| **Phase 1: Architecture & Schema Planning** | 1.5 hrs | 1.25 hrs | Schema design was straightforward from the requirements. |
| **Phases 2–3: Models, Alembic & Seed Data** | 1.5 hrs | 1.5 hrs | Deterministic UUID generation in the seed script ensured repeatability. |
| **Phases 4–5: JWT Authentication & RBAC** | 1.5 hrs | 1.25 hrs | FastAPI's dependency injection simplified role enforcement. |
| **Phases 6–7: Menu & Order Lifecycle** | 2.5 hrs | 2.5 hrs | Strict state machine transitions and line voiding reasons matched estimates. |
| **Phases 8–9: Slow Alerts, Dashboard & CSV** | 2.0 hrs | 2.25 hrs | Alert reappearance calculations required additional edge-case testing. |
| **Phase 10: Frontend UI & Chart.js** | 2.0 hrs | 2.25 hrs | Polishing responsive CSS and modal workflows took slightly longer. |
| **Phase 11: Full System Integration (54 tests)** | 0.5 hrs | 0.25 hrs | Automated test runs were rapid and confirmed 100% green. |
| **Phase 12: Deployment & Documentation** | 0.5 hrs | 0.25 hrs | Render blueprint and Uvicorn commands worked seamlessly. |
| **Total** | **12.0 hrs** | **11.5 hrs** | **Completed within budget.** |

---

## What did you cut when you ran short?

All **10 core assignment goals** were delivered and verified completely. 

To maintain strict delivery discipline within the 12-hour budget, we deliberately cut all **optional stretch ideas** explicitly listed in `README.md` lines 81–95:
1. *Kitchen display screen (KDS):* Substituted by real-time order status tracking in the UI.
2. *Handheld table-side ordering:* Waiter responsive UI works on mobile viewports, but dedicated handheld hardware integrations were skipped.
3. *Split checks across multiple payers:* Orders maintain a single running total.
4. *Loyalty / repeat-customer programs:* Customer identities are anonymous at table level.
5. *Ingredient-level stock deduction:* Availability managed cleanly at dish level via `menu_items.is_available`.
6. *Printable / emailed receipts:* Bills displayed on screen and exported via CSV.

Focusing 100% of the time budget on meeting all 10 core requirements solidly ensured high code quality, comprehensive test coverage (54 tests), and production stability.
