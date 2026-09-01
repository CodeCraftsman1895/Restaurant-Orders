# Restaurant Order Management System - Frontend

A professional, responsive, and role-aware frontend interface for the Restaurant Order Management System, built with Vanilla HTML5, modern CSS3, ES6 JavaScript, and Chart.js.

---

## 📁 Directory Structure

```
frontend/
├── index.html            # Main entry point & role-aware router/redirector
├── login.html            # Authentication page with quick demo account logins
├── orders.html           # Dining room order queue with server-side filters & creation modal
├── order-details.html    # Detailed order view with status workflow, lines, voiding & audit timeline
├── menu.html             # Menu catalog with real-time availability toggles & Goal 7 bulk actions
├── alerts.html           # Live slow-order alerts list with instant acknowledgment
├── dashboard.html        # Manager dashboard with KPI cards, 14-day Chart.js & CSV export
├── css/
│   ├── style.css         # Master design system, variables, navbar, modals, toasts & status badges
│   ├── orders.css        # Order queue and filter toolbar layout
│   ├── menu.css          # Dish catalog cards and Goal 7 floating bulk actions bar
│   ├── alerts.css        # Slow-order alert cards and duration badges
│   └── dashboard.css     # KPI cards and Chart.js container layout
└── js/
    ├── api.js            # Reusable Fetch API layer with JWT injection and error handling
    ├── auth.js           # Authentication, session caching, and route protection
    ├── utils.js          # Formatters, toast notifications, modals, and navbar badge poller
    ├── orders.js         # Order list controller with server-side pagination and order creation
    ├── order-details.js  # Order actions controller (lines, voiding, status workflow, timeline)
    ├── menu.js           # Menu CRUD, availability toggles, and Goal 7 bulk updates
    ├── alerts.js         # Slow-order alert controller with real-time dismissals
    └── dashboard.js      # Manager dashboard controller with Chart.js visualization & CSV export
```

---

## 🚀 Key Features by Page

### 1. Authentication (`login.html`)
* Secure sign-in via `POST /api/auth/login`.
* Caches user profile via `GET /api/auth/me`.
* Quick-fill demo account buttons (`Sarah Manager`, `Alice Johnson`, `Bob Smith`).

### 2. Order Queue (`orders.html`)
* **Goal 2 & Goal 6**: Server-side table number search, status filter (`placed`, `accepted`, `preparing`, `ready`, `served`, `cancelled`), sorting, and pagination.
* "+ New Order" modal: Table number input, dynamic dish selection from live `/api/menu`, item notes, and client-side running total preview.

### 3. Order Details & Management (`order-details.html`)
* **Goal 4 Status Transitions**: Interactive lifecycle buttons enforcing state machine rules (`placed` $\rightarrow$ `accepted` $\rightarrow$ `preparing` $\rightarrow$ `ready` $\rightarrow$ `served`). Prevents cancellation once in `preparing`.
* **Goal 3 & 4 Line Items & Voiding**: View dish lines with captured price snapshots; void individual lines with a mandatory explanatory reason.
* **Goal 5 Collaborators**: View, add, and remove collaborating waiters.
* **Goal 9 Immutable Timeline**: Chronological audit trail of all status transitions, lines added/voided, and table notes with user attribution.

### 4. Menu Management (`menu.html`)
* **Goal 1 & Goal 7**: View dish catalog with availability toggles (`Available`, `Unavailable`, `Archived`).
* Manager tools: Add dishes, edit prices, archive/restore dishes.
* **Goal 7 Bulk Actions**: Select multiple dishes, apply price/availability changes in a single action, and view per-item success/failure reporting with specific reasons.

### 5. Slow-Order Alerts (`alerts.html`)
* **Goal 10 Dynamic Badges & Alerts**: Live navigation badge count polled periodically.
* Alert list displays table number, duration open (in minutes), primary waiter, and collaborators.
* "Acknowledge" button instantly dismisses the alert and suppresses it for the configured reappear interval.
* Highlights unresolved reappeared alerts.

### 6. Manager Dashboard (`dashboard.html`)
* **Goal 8 KPI Analytics**: Real-time cards for Today's Revenue, Open Orders, Orders Placed Today, and Served Orders Today.
* **14-Day Served Orders Chart**: Interactive dual-axis Chart.js bar & line chart visualizing daily served volume and gross receipts.
* **Breakdown Tables**: Order counts by lifecycle status and waiter activity & revenue.
* **Goal 1 & 8 CSV Export**: Downloads a server-generated CSV matching active filter criteria.

---

## 🔒 Security & Authorization
* Frontend navigation dynamically adjusts based on user role (`manager` vs `waiter`).
* All security and permission rules are strictly enforced by the backend API (`401` on unauthenticated requests, `403` on unauthorized actions).
* No secrets, tokens, or database credentials are exposed in source code.
