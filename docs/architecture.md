# Architecture Documentation - Restaurant Order Management System

## 1. System Components & Interaction

The Restaurant Order Management System is designed around a decoupled, layered architecture:

```
┌────────────────────────────────────────────────────────┐
│                   CLIENT BROWSER                       │
│  HTML5 + Modern CSS3 + Vanilla JavaScript + Chart.js   │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTPS / JSON / JWT
                           ▼
┌────────────────────────────────────────────────────────┐
│                 FASTAPI APPLICATION                    │
│  - JWT Authentication & RBAC Layer                     │
│  - Domain Services (Orders, Menu, Alerts, Dashboard)   │
│  - Static Asset Serving & CORS Middleware              │
└──────────────────────────┬─────────────────────────────┘
                           │ SQLAlchemy 2.0 / SSL
                           ▼
┌────────────────────────────────────────────────────────┐
│              SUPABASE POSTGRESQL (HOSTED)              │
│  7-Table Relational Schema + Foreign Keys & Indicies   │
└────────────────────────────────────────────────────────┘
```

### Key Components:
1. **Frontend Layer:** Vanilla HTML5/CSS3/JavaScript (ES6 Modules) using Fetch API and Chart.js for data visualization. Contains zero build-step complexity or heavy frameworks.
2. **Backend API Layer:** FastAPI (Python 3.12) exposing structured REST endpoints under `/api`. Enforces JWT authentication, server-side RBAC, price snapshot preservation, order lifecycle state machines, and CSV streaming.
3. **Database Layer:** Hosted Supabase PostgreSQL instance with connection pooling, Alembic migration management, and strict relational integrity across 7 core application tables.

---

## 2. Where Each Piece Runs

* **Database:** Hosted in cloud on Supabase PostgreSQL (`aws-0-ap-northeast-1.pooler.supabase.com:5432`) with SSL enabled.
* **Backend API:** Hosted as a Python Web Service on Render / Railway / Koyeb / Fly.io container using `uvicorn` as the ASGI production server.
* **Frontend UI:** Served statically by the FastAPI ASGI application (or optionally via Netlify / Vercel / Cloudflare Pages) directly to web browsers on desktop, tablet, and mobile viewports.

---

## 3. End-to-End Request Path (Representative User Action)

### Scenario: *Waiter Alice creates a new order for Table 12 with 2x Cheeseburger Deluxe.*

1. **User Action:** The waiter selects Table 12, chooses "Cheeseburger Deluxe" (quantity 2), and clicks "Create Order".
2. **Client Request:** `frontend/js/orders.js` invokes `api.post("/api/orders", { table_number: 12, lines: [...] })`, attaching `Authorization: Bearer <jwt_token>`.
3. **Authentication & Authorization:** FastAPI's `get_current_user` dependency validates the JWT signature (HS256) and extracts Alice's user profile (`role: waiter`).
4. **Business Logic & Service Layer:** `OrderService.create_order` is executed:
   - Validates that Table 12 is a positive integer.
   - Sets Alice as the `primary_waiter_id` and initial status as `placed`.
   - Inspects `menu_items` to confirm the item is active and available.
   - Captures the exact unit price snapshot (`unit_price: 15.00`) directly from the menu item record.
   - Writes an immutable `OrderEvent` (`status_change: placed`) into `order_events`.
5. **Database Transaction:** SQLAlchemy flushes the transaction, assigns UUIDs, and commits atomically to Supabase PostgreSQL.
6. **API Response:** FastAPI serializes the `OrderResponse` Pydantic model with calculated totals and returns `HTTP 201 Created`.
7. **Frontend Update:** `orders.js` receives the response, shows a success toast, closes the modal, and refreshes the live queue.

---

## 4. What Was Decided *NOT* to Build and Why

* **No Frontend Frameworks (React, Vue, Angular):** Kept frontend in Vanilla HTML/CSS/JS to guarantee zero build steps, instant load times, and ease of maintainability.
* **No Client-Side Business Rules:** Price calculation, running totals, slow-order duration checks, and lifecycle constraints are strictly calculated and validated on the backend to prevent security bypass.
* **No Database Schema Alterations:** Strict adherence to the documented 7-table schema; avoided creating unnecessary inventory or ingredients tables beyond the assignment specification.
