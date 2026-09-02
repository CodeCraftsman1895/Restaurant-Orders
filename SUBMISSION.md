# Submission

## Links

- **GitHub repository:** https://github.com/CodeCraftsman1895/Restaurant-Orders
- **Live application:** https://restaurant-orders-api-dhnd.onrender.com
- **API Documentation (Swagger):** https://restaurant-orders-api-dhnd.onrender.com/api/docs
- **OpenAPI JSON:** https://restaurant-orders-api-dhnd.onrender.com/api/openapi.json

## Notes for the reviewer

The backend API and static frontend are hosted on a single **Render Free Web Service** connected to a hosted **Supabase PostgreSQL** database.

> [!NOTE]
> **Render Free Tier Cold Starts:**  
> Free web services on Render automatically spin down when idle. If the application has not received traffic in the last 15 minutes, the very first HTTP request may take **30 to 60 seconds** to wake up. Once active, the application responds instantly.

## Demo credentials

The database is pre-seeded with full demo accounts and historical data:

| Role | Email | Password | Permissions |
|---|---|---|---|
| **Manager** | `manager@restaurant.com` | `manager123` | Full access: Dashboard KPIs, 14-day chart, CSV export, menu catalog CRUD & Goal 7 bulk updates, all orders. |
| **Waiter** | `alice@restaurant.com` | `waiter123` | Order operations: Create orders, add dish lines, void lines with reasons, collaborate, manage table lifecycle, slow alerts. |
| **Waiter** | `bob@restaurant.com` | `waiter123` | Order operations and multi-waiter collaboration partner on assigned tables. |
| **Waiter** | `carol@restaurant.com` | `waiter123` | Additional dining room waiter for testing collaboration views. |

*(For testing convenience, the login page features one-click demo quick-fill buttons for Manager and Waiter roles).*

## Stack

| Layer | What you used | Why |
|---|---|---|
| **Frontend** | HTML5, Modern CSS3, Vanilla JavaScript (ES6+), Chart.js | Zero build steps or compilation overhead; instant load times; clean separation of presentation from API; avoids framework hydration and state synchronization bloat. |
| **Backend** | Python 3.12, FastAPI, Uvicorn | High-performance asynchronous REST API framework; automatic OpenAPI documentation; robust Pydantic data validation; clean dependency-injection architecture for auth and RBAC. |
| **Database** | PostgreSQL 15 (Supabase Cloud), SQLAlchemy 2.0 ORM, Alembic | Industry-standard ACID-compliant relational storage; foreign key cascading; strict database constraints (prices, quantities, table numbers, valid roles/statuses); 17 B-Tree indexes for fast filtering and pagination. |
| **Hosting** | Render (Web Service), Supabase (Managed Postgres) | Reliable free-tier hosting pairing a managed cloud database with containerized Python PaaS web deployment. |

## Goal checklist

| # | Goal | Status | Notes |
|---|---|---|---|
| 1 | Accounts and roles | Done | Bcrypt password hashing, JWT bearer tokens, server-enforced `manager` and `waiter` roles, object-level order access checks. |
| 2 | Orders | Done | Orders tied to table numbers with primary waiter assignment; non-destructive archiving and restoring without deleting history. |
| 3 | Order lines | Done | Unit price snapshots stored permanently on order lines at creation time; running total dynamically calculated excluding voided items. |
| 4 | Order lifecycle with rules | Done | Strict state machine (*Placed → Accepted → Preparing → Ready → Served*); cancellation strictly blocked once in *Preparing*; line voiding with required reason while order is open. |
| 5 | Collaborators | Done | Multi-waiter collaboration via `order_collaborators`; shared order management; consolidated waiter order queue. |
| 6 | Finding orders | Done | Server-side text search over table numbers, filters for status/waiter/date, dynamic sorting, and server-side pagination with total match counts. |
| 7 | Acting on many menu items at once | Done | Bulk menu price and availability updates with itemized per-item success/failure reporting; daily orders CSV streaming export. |
| 8 | A dashboard | Done | Headline KPIs (open orders, placed today, served today, revenue today); status and waiter breakdowns; 14-day continuous served orders Chart.js trendline. |
| 9 | History you cannot rewrite | Done | Append-only immutable `order_events` audit table logging all status transitions (with old/new values), line additions, voidings with reasons, and notes. No update/delete endpoints. |
| 10 | Slow-order alerts | Done | Dynamic slow-order detection for orders open $\ge 15$ minutes without reaching *Ready*; navigation count badge; acknowledgment snooze suppression; reappearance after 10 minutes if unresolved. |

## How much time did you actually spend?

Approximately **11.5 hours** total, paced across structured sessions:
- Architecture & Schema Design: ~1.25 hours
- Models, Migrations & Deterministic Seed Data: ~1.5 hours
- JWT Authentication & Server RBAC: ~1.25 hours
- Menu & Order Lifecycle Operations: ~2.5 hours
- Slow-Order Alerts, Dashboard & CSV Export: ~2.25 hours
- Responsive Frontend UI & Chart.js Integration: ~2.25 hours
- System Verification (54 automated tests) & Deployment: ~0.5 hours

## What would you do next, with another 12 hours?

1. **Live Kitchen Display Screen (KDS):** Build a dedicated full-screen kitchen display interface utilizing WebSockets to push real-time order status updates and dish tickets to kitchen stations without polling.
2. **In-Memory Alert Queue (Redis):** For 100x scale, migrate the dynamic slow-order SQL queries to an in-memory Redis sorted set / TTL worker to offload polling traffic from PostgreSQL.
3. **Table Floor Map:** Create an interactive visual dining room floor plan allowing staff to click graphical tables to view orders and seated statuses.

## What are you least happy with in this codebase, and why?

The dynamic SQL query used for **Goal 10 Slow-Order Alerts**:
* **Why:** The navigation badge polls `/api/alerts/badge` on an interval. While our composite index `(status, created_at)` keeps query latency under 2ms for our active database, at 100x concurrency (e.g., thousands of simultaneous staff connections across dozens of locations), repeated database polling for slow orders is less optimal than an event-driven pub/sub architecture (e.g., PostgreSQL `LISTEN/NOTIFY` or Redis Pub/Sub pushing notifications over WebSockets only when an alert condition is met).
