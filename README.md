# Restaurant Orders

A modern, full-stack restaurant order management and kitchen tracking system that replaces paper tickets and chalkboard menus with real-time digital ordering, price snapshots, lifecycle state enforcement, multi-waiter collaboration, slow-order alert snoozing, manager revenue analytics, and immutable audit logs.

---

## Live Deployment & Links

* **Live Web Application:** [https://restaurant-orders-api-dhnd.onrender.com](https://restaurant-orders-api-dhnd.onrender.com)
* **Interactive API Documentation (Swagger):** [https://restaurant-orders-api-dhnd.onrender.com/api/docs](https://restaurant-orders-api-dhnd.onrender.com/api/docs)
* **OpenAPI Specification (JSON):** [https://restaurant-orders-api-dhnd.onrender.com/api/openapi.json](https://restaurant-orders-api-dhnd.onrender.com/api/openapi.json)
* **GitHub Repository:** [https://github.com/CodeCraftsman1895/Restaurant-Orders](https://github.com/CodeCraftsman1895/Restaurant-Orders)

> [!NOTE]
> **Free Hosting Wake-up:**  
> Hosted on Render's free tier. If the service is idle, the initial page load may take 30–60 seconds for the container to spin up. Subsequent interactions respond instantly.

---

## Project Overview

In a traditional busy independent restaurant, orders are handwritten on paper slips and pinned to a kitchen corkboard, while the menu and daily specials live on a chalkboard. When a paper ticket falls off, an order never reaches the cooks, leaving diners stranded. When menu prices change on the chalkboard, two customers at the same table may be charged different amounts for the same dish. Furthermore, dining room staff have no way of knowing how long an order has been sitting without walking into the kitchen.

This application provides a unified, real-time digital system:
1. **Managers** maintain menu items, set prices, toggle real-time ingredient availability, execute Goal 7 bulk adjustments, view revenue analytics, and export daily CSV reports.
2. **Waiters** create table orders, add dishes, capture permanent unit price snapshots, void mistakes with mandatory reasons, collaborate across busy tables, and track live order progress.
3. **Kitchen & Floor Staff** monitor order states (*Placed $\rightarrow$ Accepted $\rightarrow$ Preparing $\rightarrow$ Ready $\rightarrow$ Served*), receive automated navigation alert badges for slow orders ($\ge 15$ min), and snooze alerts with automatic 10-minute reappearances if unresolved.

---

## Assignment Context

This application was engineered for the **Restaurant Orders (Take-Home 09)** engineering assessment.

The original assignment brief, requirements, and assessment criteria are permanently preserved in:
👉 [`docs/assignment/README.md`](docs/assignment/README.md)

---

## Core Features (All 10 Assignment Goals)

1. **Accounts & Roles (Goal 1):** Sign in with email and password. Two distinct roles (`manager` and `waiter`) enforced strictly on the server via FastAPI dependency injection and database check constraints.
2. **Orders (Goal 2):** Create orders by positive table number; creator is automatically assigned as the primary waiter. Non-destructive archiving and restoring hides old tickets from the active queue while preserving history.
3. **Order Lines & Price Snapshots (Goal 3):** Attach dishes, quantities, and special cooking instructions to an order. The server captures a permanent **unit price snapshot** at insertion time, ensuring future menu price edits never corrupt past customer receipts or accounting totals.
4. **Order Lifecycle with Rules (Goal 4):** Strict state machine progression (*Placed $\rightarrow$ Accepted $\rightarrow$ Preparing $\rightarrow$ Ready $\rightarrow$ Served*). Cancellation is blocked once the kitchen begins *Preparing*. Individual lines can be voided with a mandatory explanatory reason while the order remains open.
5. **Collaborators (Goal 5):** Primary waiters can add any number of collaborating waiters to share order updates. Waiters view a consolidated queue of their primary and collaborated tables.
6. **Finding Orders (Goal 6):** High-performance server-side table search, filtering by status, waiter, and date range, sorting, and pagination with total match counts. Zero client-side filtering.
7. **Bulk Menu Actions & CSV Export (Goal 7):** Managers can select multiple dishes and apply price or availability changes in a single action, returning an itemized per-item success/failure report. Separately, export the day's orders as a streaming CSV file.
8. **Manager Dashboard (Goal 8):** Real-time KPI summary (open orders, today's seated orders, today's served orders, today's served revenue), status and waiter volume breakdowns, and a continuous 14-day served orders trendline powered by Chart.js.
9. **Immutable Audit History (Goal 9):** Append-only event timeline logging every status transition (with actor and old/new states), line addition, line voiding with required reason, and table notes. Cannot be altered or deleted, even by managers.
10. **Slow-Order Alerts (Goal 10):** Dynamic alert engine detecting orders open $\ge 15$ minutes without reaching *Ready*. Displays a real-time navigation count badge, supports one-click acknowledgment suppression, and automatically re-alerts after 10 minutes if the order remains unready.

---

## Technology Stack

* **Backend:** Python 3.12, FastAPI, Uvicorn (ASGI)
* **Database & ORM:** PostgreSQL 15 (Supabase Cloud), SQLAlchemy 2.0, Alembic (Migrations)
* **Frontend:** Vanilla HTML5, Modern CSS3 variables, ES6+ JavaScript (Fetch API), Chart.js
* **Security:** Bcrypt password hashing, PyJWT (HS256 tokens), OAuth2 Bearer flow
* **Testing:** Pytest 8.0+, HTTPX (TestClient)
* **Hosting:** Render (Linux PaaS container), Supabase (Managed PostgreSQL)

---

## Architecture & Data Flow

The system employs a 3-tier, decoupled architecture where presentation, business logic, and persistence are strictly segregated:

```
┌────────────────────────────────────────────────────────┐
│                   CLIENT BROWSER                       │
│  HTML5 + Modern CSS3 + Vanilla JavaScript + Chart.js   │
│  (Served statically by the FastAPI ASGI application)   │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTPS / JSON / JWT
                           ▼
┌────────────────────────────────────────────────────────┐
│                 FASTAPI REST API LAYER                 │
│  - JWT Bearer Authentication & RBAC Dependencies       │
│  - Domain Services (Orders, Menu, Alerts, Analytics)   │
│  - Static Asset Mounting & CORS Middleware             │
└──────────────────────────┬─────────────────────────────┘
                           │ SQLAlchemy 2.0 / SSL
                           ▼
┌────────────────────────────────────────────────────────┐
│              SUPABASE POSTGRESQL DATABASE              │
│  7 Relational Tables + Check Constraints + 17 Indexes  │
└────────────────────────────────────────────────────────┘
```

Detailed architectural diagrams and request path traces are documented in [`docs/architecture.md`](docs/architecture.md).

---

## Project Structure

```text
Restaurant-Orders/
├── backend/
│   ├── alembic/              # Database migration environment & versions
│   │   └── versions/         # edd2eac79e58_initial_schema.py
│   ├── app/
│   │   ├── core/             # Configuration, JWT security, dependencies, RBAC
│   │   ├── database/         # Engine connection, Base class, session factory
│   │   ├── models/           # 7 SQLAlchemy mapped ORM models
│   │   ├── routers/          # REST endpoints (auth, menu, orders, alerts, dashboard)
│   │   ├── schemas/          # Pydantic request/response validation schemas
│   │   ├── services/         # Business logic layer (state machine, pricing, alerts)
│   │   └── main.py           # FastAPI entry point & static file mount
│   ├── seed/                 # Deterministic, repeatable seed data generator
│   ├── tests/                # 54 automated pytest tests across all modules
│   └── requirements.txt      # Production Python dependencies
├── frontend/
│   ├── css/                  # Modular styles (style.css, orders.css, menu.css, etc.)
│   ├── js/                   # Vanilla controllers (api.js, auth.js, orders.js, etc.)
│   ├── index.html            # Role-aware router
│   ├── login.html            # Staff sign-in & demo quick-fill cards
│   ├── orders.html           # Active dining room queue & table search
│   ├── order-details.html    # Order view, voiding modal, collaborators, timeline
│   ├── menu.html             # Dish catalog & Goal 7 bulk actions
│   ├── alerts.html           # Slow orders & acknowledgment controls
│   └── dashboard.html        # Manager KPIs, Chart.js trendline & CSV export
├── docs/
│   ├── architecture.md       # Moving pieces, request flows, exclusions
│   ├── schema.md             # 7-table schema, 17 indexes, 100x scale analysis
│   ├── plan.md               # Session breakdown, build order, actual time
│   ├── decisions.md          # 5 architectural decisions & reversed decision
│   ├── ai-prompts.md         # AI prompt history & documented error fix
│   └── assignment/           # Preserved original assignment specification
├── Dockerfile                # Multi-stage production container
├── Procfile                  # PaaS web process command
├── render.yaml               # Render cloud deployment blueprint
└── SUBMISSION.md             # Candidate submission declaration & checklist
```

---

## Database Schema (7 Core Tables)

Designed for PostgreSQL with UUIDv4 primary keys, foreign key cascading, check constraints, and 17 B-Tree indexes:

1. `users` — Staff accounts, bcrypt password hashes, and server roles (`manager`, `waiter`).
2. `menu_items` — Restaurant dishes, base prices, active toggle, and availability state.
3. `orders` — Dining table orders, table numbers, primary waiter creator, status, archive flag.
4. `order_lines` — Dishes ordered, quantities, instructions, void status, void reason, and **unit price snapshots**.
5. `order_collaborators` — Many-to-many junction linking orders with additional collaborating waiters.
6. `order_events` — Append-only immutable audit log recording transitions, voids, line additions, and notes.
7. `alert_acknowledgments` — Timestamps and staff records for acknowledged slow-order alerts.

Complete column types, constraints, and relationship cardinalities are documented in [`docs/schema.md`](docs/schema.md).

---

## Demo Accounts & Credentials

The production database is seeded with complete demo data. The login page includes one-click demo buttons for testing:

| Role | Email | Password | Access Capabilities |
|---|---|---|---|
| **Manager** | `manager@restaurant.com` | `manager123` | Dashboard KPIs, 14-day chart, CSV export, menu catalog CRUD, Goal 7 bulk updates, all orders. |
| **Waiter** | `alice@restaurant.com` | `waiter123` | Order operations: Create tables, add lines, void with reasons, collaborate, slow alerts. |
| **Waiter** | `bob@restaurant.com` | `waiter123` | Dining room table management & collaboration partner. |
| **Waiter** | `carol@restaurant.com` | `waiter123` | Additional dining room waiter for testing collaboration views. |

*(Note: These are pre-seeded demonstration credentials; production credentials and secrets are managed via environment variables).*

---

## Verification & Automated Testing

The complete system has been verified with **54 automated unit and integration tests** across 8 test suites:

```text
============================= test session starts =============================
test_db_connection.py::test_connection PASSED                            [  1%]
tests/test_alerts.py (7 tests) PASSED                                    [ 14%]
tests/test_auth.py (9 tests) PASSED                                      [ 31%]
tests/test_dashboard.py (6 tests) PASSED                                 [ 42%]
tests/test_frontend_integration.py (2 tests) PASSED                      [ 46%]
tests/test_menu.py (13 tests) PASSED                                     [ 70%]
tests/test_orders.py (9 tests) PASSED                                    [ 87%]
tests/test_permissions.py (7 tests) PASSED                               [100%]
============================== 54 passed in 189s ==============================
```

To run tests locally:
```bash
cd backend
pytest -v
```

---

## Environment Variables

Production environment configuration (values are kept secret and never committed):

* `DATABASE_URL` — PostgreSQL connection URI (e.g. Supabase pooler connection string with SSL).
* `SECRET_KEY` — Cryptographic key for signing JWT tokens.
* `ALGORITHM` — Token signing algorithm (default: `HS256`).
* `ACCESS_TOKEN_EXPIRE_MINUTES` — Token lifetime in minutes (default: `1440` / 24 hours).
* `ALERT_THRESHOLD_MINUTES` — Slow-order alert trigger threshold (default: `15`).
* `ALERT_REAPPEAR_MINUTES` — Snoozed alert reappearance interval (default: `10`).
* `CORS_ORIGINS` — Comma-separated list of allowed origins.

---

## Local Development Setup

1. **Clone repository:**
   ```bash
   git clone https://github.com/CodeCraftsman1895/Restaurant-Orders.git
   cd Restaurant-Orders
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Create `.env` in `backend/` with your `DATABASE_URL` and `SECRET_KEY`.

4. **Run Migrations & Seed:**
   ```bash
   alembic upgrade head
   python seed/seed_data.py
   ```

5. **Start Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Open `http://localhost:8000` in your web browser.

---

## Assignment Compliance Summary

| Goal | Requirement | Status | Verification Evidence |
|:---:|---|:---:|---|
| **1** | Accounts & roles (`manager`, `waiter`, server RBAC) | ✅ Complete | `app/core/dependencies.py`, `test_auth.py`, `test_permissions.py` |
| **2** | Orders (table numbers, primary waiter, archiving) | ✅ Complete | `app/services/order_service.py`, `orders.html`, `test_orders.py` |
| **3** | Order lines (price snapshots, running totals) | ✅ Complete | `app/models/order_line.py`, `order-details.html`, `test_orders.py` |
| **4** | Lifecycle state machine & line voiding with reasons | ✅ Complete | `app/services/order_service.py`, `test_orders.py` |
| **5** | Multi-waiter collaboration | ✅ Complete | `app/models/collaborator.py`, `test_orders.py` |
| **6** | Finding orders (server-side search, filters, pagination) | ✅ Complete | `app/services/order_service.py`, `orders.html`, `test_orders.py` |
| **7** | Bulk menu updates (per-item results) & CSV export | ✅ Complete | `app/services/menu_service.py`, `test_menu.py`, `test_dashboard.py` |
| **8** | Manager dashboard, served revenue & 14-day Chart.js | ✅ Complete | `app/services/dashboard_service.py`, `dashboard.html`, `test_dashboard.py` |
| **9** | Immutable audit timeline (`order_events`) | ✅ Complete | `app/services/event_service.py`, `order-details.html`, `test_orders.py` |
| **10** | Slow-order alerts (15m threshold, badge, snooze) | ✅ Complete | `app/services/alert_service.py`, `alerts.html`, `test_alerts.py` |

---

## Deliberate Exclusions (Optional Stretch Goals)

As permitted by the assignment brief, optional stretch ideas were intentionally excluded to focus on the 10 required goals:
* Kitchen display screen (KDS)
* Table-side handheld ordering hardware integrations
* Split checks across multiple diners
* Customer loyalty / points programs
* Ingredient-level raw stock deduction
* Printable / emailed receipts
