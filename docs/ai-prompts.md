# AI Prompts & Workflow Log

This document records the AI prompts and engineering iterations used during the development of the Restaurant Orders application, grouped by development phase, including documented errors, corrections, and verification steps.

---

## 1. Project Planning & Schema Design (Phase 1)

### Prompt
> *"Inspect the assignment README and design an implementation-ready relational schema for PostgreSQL. Identify all 10 core goals and map them to tables, foreign keys, constraints, and indexes. We need exactly 7 tables without unnecessary bloat like recipe inventory. Also explain what breaks at 100x scale."*

### What We Got
The AI produced a 7-table schema definition with UUID primary keys, check constraints on price, quantity, and table number, and an indexing plan.

### What Was Corrected
The initial draft suggested adding an `order_lines.total_price` column. We corrected this to store only `order_lines.unit_price` (the snapshot) and `order_lines.quantity`, computing line total dynamically as `quantity * unit_price` to maintain a single source of truth for the line's math.

---

## 2. Models, Alembic & Seed Data (Phases 2–3)

### Prompt
> *"Generate SQLAlchemy 2.0 mapped models for the 7 tables. Then write an Alembic migration script and an idempotent seed script that populates demo accounts (Sarah Manager, Alice Waiter, Bob Waiter, Carol Waiter), 15 menu items, 12 core orders testing all states, and 14 days of backdated served orders for the dashboard chart."*

### What We Got
SQLAlchemy models using `Mapped` and `mapped_column`, an Alembic migration, and a seed script.

### What Was Corrected
The initial seed script used `uuid.uuid4()` randomly, which created duplicate rows every time the seed was run. We instructed the AI to use **`uuid.uuid5` with a deterministic namespace** (`NAMESPACE_SEED = uuid.UUID("...")`), guaranteeing that running the seed script multiple times safely updates records without primary key collisions.

---

## 3. Authentication & RBAC (Phases 4–5)

### Prompt
> *"Implement JWT authentication with bcrypt password hashing in FastAPI. Provide POST /api/auth/login and GET /api/auth/me. Then create reusable dependency functions require_manager and require_waiter_or_manager that reject unauthorized access with HTTP 403. Write pytest suites for auth and permissions."*

### What We Got
Clean authentication router, security utilities (`verify_password`, `create_access_token`, `decode_access_token`), and dependency factories.

### What Was Corrected
The initial test client in `test_permissions.py` attempted to define a dynamic router on the shared `app` instance after static files had been mounted, triggering route conflict warnings. We corrected the test to use an isolated test FastAPI application instance for authorization unit tests.

---

## 4. Order Lifecycle & Line Voiding (Phase 7)

### Prompt
> *"Implement order management according to Goal 4. Orders progress Placed -> Accepted -> Preparing -> Ready -> Served. Block whole-order cancellation once status is Preparing with HTTP 400. Allow voiding individual lines with a required void reason while the order is open. Log all transitions, line additions, and voids into order_events."*

### What We Got
A state machine dictionary `VALID_TRANSITIONS` and service methods for status updates, line additions, and line voiding.

### What Was Corrected
The initial line-voiding implementation allowed voiding without checking whether the order was in `served` or `cancelled` terminal state. We corrected the logic to enforce that order lines can only be voided while the order remains open, raising `HTTP 400` if the order is already completed.

---

## 5. Slow-Order Alerts & Reappearance (Phase 8) — Documented Error & Fix

### Prompt
> *"Implement Goal 10 slow-order alerts. Orders open >= 15 minutes without reaching Ready must appear in alerts with a navbar badge count. Staff can acknowledge an alert to clear it. If the order is still not Ready 10 minutes later, the alert must return."*

### What We Got (The Error)
The AI's first draft proposed deleting the acknowledgment record from `alert_acknowledgments` whenever the order status changed or when the 10-minute window passed.

### Why This Was Wrong
1. Deleting records destroyed the audit history of who acknowledged the alert and when.
2. It created race conditions where the system could not determine whether an alert was brand new or returning after a snooze.

### What We Corrected
We rejected the deletion approach and refactored `AlertService.get_slow_orders` to keep `alert_acknowledgments` **append-only**:
* We query the most recent acknowledgment (`max(acknowledged_at)`).
* If `time_since_ack < 10 minutes` $\rightarrow$ **Suppress** alert (`is_suppressed = True`).
* If `time_since_ack >= 10 minutes` $\rightarrow$ **Re-Alert** (`is_reappeared = True`), tagging the alert card with an amber "⚠️ Reappeared Alert" warning while preserving the historical timestamp and staff attribution.

---

## 6. Dashboard, Revenue & CSV Export (Phase 9)

### Prompt
> *"Build the manager dashboard analytics and CSV export API for Goal 8. Calculate headline numbers: open orders, placed today, served today, and today's revenue. Build a continuous 14-day served orders time-series. Provide a streaming CSV export endpoint."*

### What We Got
`DashboardService` and `GET /api/dashboard/export`.

### What Was Corrected
Today's revenue calculation initially summed all orders placed today. We corrected the SQL query to sum only non-voided lines on orders with `status == 'served'` and `updated_at >= today_start`, ensuring unserved and cancelled tickets are excluded from commercial revenue.

---

## 7. Frontend UI & Integration (Phases 10–12)

### Prompt
> *"Build a responsive Vanilla HTML5/CSS3/JavaScript frontend with Chart.js. Provide views for Login, Order Queue, Order Details with voiding modals, Menu Management with Goal 7 bulk actions, Alerts, and Dashboard. Avoid React or build tools. Mount static files in FastAPI."*

### What We Got
7 modular HTML views, cohesive CSS stylesheets, and ES6 JavaScript controllers communicating with the FastAPI backend via Fetch API.

### What Was Corrected
The API client base URL initially defaulted strictly to `http://localhost:8000`. We updated `frontend/js/api.js` to resolve dynamically: using `window.location.origin` when hosted together on Render, while supporting `window.__API_URL__` for standalone hosting.
