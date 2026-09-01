# Database Schema Specification

This document provides the authoritative, implementation-ready relational database schema design for the **Restaurant Orders** management system, derived strictly from the requirements in `README.md`.

---

## 1. Schema Overview

The database is designed for **PostgreSQL 15+** utilizing **UUIDv4** primary keys, relational integrity with foreign keys, column constraints, composite indexes for high-frequency queries, and immutable audit logs.

The architecture comprises **7 core tables**:

1. `users` — Authentication, user accounts, and role assignment (`manager` vs `waiter`).
2. `menu_items` — Restaurant menu items with price, real-time availability toggle, and retirement/archiving.
3. `orders` — Dine-in table orders, tracking lifecycle status, table number, primary waiter, and active/archived state.
4. `order_lines` — Individual items attached to an order with historical price snapshot, quantity, special instructions, and void tracking.
5. `order_collaborators` — Many-to-many junction linking orders with additional collaborating waiters.
6. `order_events` — Append-only, immutable timeline recording every status change, line addition, line voiding (with reason), and order note.
7. `alert_acknowledgments` — Timestamps and actor records for acknowledged slow-order alerts to support dynamic reappearance.

---

## 2. Requirement-to-Data Mapping

| Goal / Requirement | Data to Persist | Responsible Entity / Table | Required Fields | Relationships | Constraints & States | Persistence Explicitly Required? | Source in README |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Goal 1: Accounts & Roles** | User credentials, full name, role | `users` | `id`, `name`, `email`, `password_hash`, `role`, `created_at`, `updated_at` | 1:N with `orders`, `order_collaborators`, `order_events`, `alert_acknowledgments` | Unique email, `role IN ('manager', 'waiter')` | **YES** | Lines 28–33 |
| **Goal 2: Orders** | Table identifier, primary creator, archive state | `orders` | `id`, `table_number`, `status`, `primary_waiter_id`, `is_archived`, `created_at`, `updated_at` | N:1 with `users` (primary waiter), 1:N with `order_lines`, `order_collaborators`, `order_events` | `table_number > 0`, default `status = 'placed'`, `is_archived = FALSE` | **YES** | Lines 35–38 |
| **Goal 3: Order Lines** | Item reference, quantity, notes, historical price snapshot | `order_lines` | `id`, `order_id`, `menu_item_id`, `quantity`, `special_instructions`, `unit_price`, `is_voided`, `void_reason`, `created_at` | N:1 with `orders`, N:1 with `menu_items` | `quantity > 0`, `unit_price > 0`, default `is_voided = FALSE` | **YES** | Lines 39–43 |
| **Goal 4: Lifecycle Rules** | Forward state transitions, cancellation, void reason | `orders`, `order_lines`, `order_events` | `orders.status`, `order_lines.is_voided`, `order_lines.void_reason` | Tracked via `order_events` | `status IN ('placed', 'accepted', 'preparing', 'ready', 'served', 'cancelled')`. DB check: `(is_voided = FALSE OR void_reason IS NOT NULL)` | **YES** | Lines 44–50 |
| **Goal 5: Collaborators** | Shared waiter assignments per order | `order_collaborators` | `id`, `order_id`, `user_id`, `created_at` | N:1 with `orders`, N:1 with `users` | `UNIQUE(order_id, user_id)` | **YES** | Lines 52–55 |
| **Goal 6: Finding Orders** | Searchable table, status, waiter, date filters | `orders` | `table_number`, `status`, `primary_waiter_id`, `created_at`, `is_archived` | Join `users`, `order_collaborators` | Filtered & paginated on database server via indexes | **YES** | Lines 57–60 |
| **Goal 7: Bulk Menu Actions & CSV** | Dish price, availability, archive status; order export | `menu_items`, `orders`, `order_lines` | `menu_items.price`, `menu_items.is_available`, `menu_items.is_archived` | — | `price > 0`. Orders CSV generated via dynamic query. | **YES** | Lines 62–67 |
| **Goal 8: Dashboard** | Aggregate metrics, daily volume, revenue | `orders`, `order_lines` | `orders.status`, `orders.created_at`, `orders.updated_at`, `order_lines.unit_price`, `order_lines.quantity` | Aggregation queries across `orders` & `order_lines` | Computed live via SQL. No redundant aggregate tables. | **YES** | Lines 68–71 |
| **Goal 9: Immutable History** | Audit log of status transitions, voiding reasons, notes | `order_events` | `id`, `order_id`, `user_id`, `event_type`, `old_status`, `new_status`, `order_line_id`, `details`, `created_at` | N:1 with `orders`, N:1 with `users`, N:1 with `order_lines` (nullable) | Append-only. `event_type IN ('status_change', 'line_added', 'line_voided', 'note_added')` | **YES** | Lines 72–75 |
| **Goal 10: Slow-Order Alerts** | Alert dismissals with timestamp for re-alert computation | `alert_acknowledgments` | `id`, `order_id`, `acknowledged_by`, `acknowledged_at` | N:1 with `orders`, N:1 with `users` | Orders in `placed/accepted/preparing` past threshold. Acknowledgments track suppression window. | **YES** | Lines 76–80 |

---

## 3. Complete Table Schemas

### 3.1. `users`
Persists user credentials and server-enforced roles.

```text
TABLE: users
─────────────────────────────────────────────────────────────────────────────────────────────
Column          Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id              UUID                        NO         gen_random_uuid()   PRIMARY KEY
name            VARCHAR(100)                NO         —                   —
email           VARCHAR(255)                NO         —                   UNIQUE
password_hash   VARCHAR(255)                NO         —                   —
role            VARCHAR(20)                 NO         —                   CHECK (role IN ('manager', 'waiter'))
created_at      TIMESTAMP WITH TIME ZONE    NO         NOW()               —
updated_at      TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Indexes:**
  * `ix_users_email` ON `email` (UNIQUE) — Fast authentication lookup.
  * `ix_users_role` ON `role` — Filtering eligible waiters for collaborator assignment.

---

### 3.2. `menu_items`
Persists restaurant offerings, price structure, current item availability, and catalog archiving.

```text
TABLE: menu_items
─────────────────────────────────────────────────────────────────────────────────────────────
Column          Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id              UUID                        NO         gen_random_uuid()   PRIMARY KEY
name            VARCHAR(200)                NO         —                   —
price           NUMERIC(10, 2)              NO         —                   CHECK (price > 0)
is_available    BOOLEAN                     NO         TRUE                —
is_archived     BOOLEAN                     NO         FALSE               —
created_at      TIMESTAMP WITH TIME ZONE    NO         NOW()               —
updated_at      TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Indexes:**
  * `ix_menu_items_is_archived` ON `is_archived` — Filters active menu items.
  * `ix_menu_items_is_available` ON `is_available` — Quick filter for orderable items.

---

### 3.3. `orders`
Persists dine-in table orders, tracking the primary waiter, lifecycle status, and archive state.

```text
TABLE: orders
─────────────────────────────────────────────────────────────────────────────────────────────
Column              Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id                  UUID                        NO         gen_random_uuid()   PRIMARY KEY
table_number        INTEGER                     NO         —                   CHECK (table_number > 0)
status              VARCHAR(20)                 NO         'placed'            CHECK (status IN ('placed', 'accepted', 'preparing', 'ready', 'served', 'cancelled'))
primary_waiter_id   UUID                        NO         —                   FOREIGN KEY → users(id) ON DELETE RESTRICT
is_archived         BOOLEAN                     NO         FALSE               —
created_at          TIMESTAMP WITH TIME ZONE    NO         NOW()               —
updated_at          TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Foreign Keys:**
  * `primary_waiter_id` REFERENCES `users(id)` ON DELETE RESTRICT (prevents deleting active staff with orders).
* **Indexes:**
  * `ix_orders_status` ON `status` — Status filtering and dashboard metrics.
  * `ix_orders_table_number` ON `table_number` — Search by table number.
  * `ix_orders_created_at` ON `created_at` — Date filtering, sorting, CSV export, dashboard.
  * `ix_orders_primary_waiter_id` ON `primary_waiter_id` — Filtering orders by waiter.
  * `ix_orders_is_archived` ON `is_archived` — Segregating active queue from archived history.
  * `ix_orders_status_created` ON `(status, created_at)` — Composite index for slow-order alert queries.

---

### 3.4. `order_lines`
Persists individual dish selections on an order, price snapshots, and void state.

```text
TABLE: order_lines
─────────────────────────────────────────────────────────────────────────────────────────────
Column                  Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id                      UUID                        NO         gen_random_uuid()   PRIMARY KEY
order_id                UUID                        NO         —                   FOREIGN KEY → orders(id) ON DELETE CASCADE
menu_item_id            UUID                        NO         —                   FOREIGN KEY → menu_items(id) ON DELETE RESTRICT
quantity                INTEGER                     NO         —                   CHECK (quantity > 0)
special_instructions    TEXT                        YES        NULL                —
unit_price              NUMERIC(10, 2)              NO         —                   CHECK (unit_price > 0)
is_voided               BOOLEAN                     NO         FALSE               —
void_reason             TEXT                        YES        NULL                —
created_at              TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Constraints:**
  * `CHECK (is_voided = FALSE OR (void_reason IS NOT NULL AND length(trim(void_reason)) > 0))` — Ensures voided items always store an explanatory reason.
* **Foreign Keys:**
  * `order_id` REFERENCES `orders(id)` ON DELETE CASCADE (order deletion cascades to lines).
  * `menu_item_id` REFERENCES `menu_items(id)` ON DELETE RESTRICT (menu items referenced in historical order lines cannot be hard deleted).
* **Indexes:**
  * `ix_order_lines_order_id` ON `order_id` — Retrieval of lines for order detail and running total.
  * `ix_order_lines_menu_item_id` ON `menu_item_id` — Menu item relationship lookup.

---

### 3.5. `order_collaborators`
Many-to-many junction linking orders with additional authorized waiters.

```text
TABLE: order_collaborators
─────────────────────────────────────────────────────────────────────────────────────────────
Column          Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id              UUID                        NO         gen_random_uuid()   PRIMARY KEY
order_id        UUID                        NO         —                   FOREIGN KEY → orders(id) ON DELETE CASCADE
user_id         UUID                        NO         —                   FOREIGN KEY → users(id) ON DELETE CASCADE
created_at      TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Constraints:**
  * `UNIQUE (order_id, user_id)` — Prevents duplicate collaborator entries on an order.
* **Foreign Keys:**
  * `order_id` REFERENCES `orders(id)` ON DELETE CASCADE.
  * `user_id` REFERENCES `users(id)` ON DELETE CASCADE.
* **Indexes:**
  * `ix_order_collaborators_order_id` ON `order_id` — Fetching collaborators for an order.
  * `ix_order_collaborators_user_id` ON `user_id` — Finding all collaborated orders for a waiter.

---

### 3.6. `order_events`
Append-only immutable audit trail recording all lifecycle transitions, line additions, voidings, and notes.

```text
TABLE: order_events
─────────────────────────────────────────────────────────────────────────────────────────────
Column          Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id              UUID                        NO         gen_random_uuid()   PRIMARY KEY
order_id        UUID                        NO         —                   FOREIGN KEY → orders(id) ON DELETE CASCADE
user_id         UUID                        NO         —                   FOREIGN KEY → users(id) ON DELETE RESTRICT
event_type      VARCHAR(30)                 NO         —                   CHECK (event_type IN ('status_change', 'line_added', 'line_voided', 'note_added'))
old_status      VARCHAR(20)                 YES        NULL                —
new_status      VARCHAR(20)                 YES        NULL                —
order_line_id   UUID                        YES        NULL                FOREIGN KEY → order_lines(id) ON DELETE SET NULL
details         TEXT                        YES        NULL                —
created_at      TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Foreign Keys:**
  * `order_id` REFERENCES `orders(id)` ON DELETE CASCADE.
  * `user_id` REFERENCES `users(id)` ON DELETE RESTRICT.
  * `order_line_id` REFERENCES `order_lines(id)` ON DELETE SET NULL.
* **Indexes:**
  * `ix_order_events_order_id` ON `order_id` — Fetching the chronological event stream for an order.
  * `ix_order_events_created_at` ON `created_at` — Sorting events chronologically.

---

### 3.7. `alert_acknowledgments`
Tracks alert dismissal events by user and timestamp to calculate suppression windows and alert reappearances.

```text
TABLE: alert_acknowledgments
─────────────────────────────────────────────────────────────────────────────────────────────
Column              Type                        Nullable   Default             Constraints
─────────────────────────────────────────────────────────────────────────────────────────────
id                  UUID                        NO         gen_random_uuid()   PRIMARY KEY
order_id            UUID                        NO         —                   FOREIGN KEY → orders(id) ON DELETE CASCADE
acknowledged_by     UUID                        NO         —                   FOREIGN KEY → users(id) ON DELETE RESTRICT
acknowledged_at     TIMESTAMP WITH TIME ZONE    NO         NOW()               —
```

* **Foreign Keys:**
  * `order_id` REFERENCES `orders(id)` ON DELETE CASCADE.
  * `acknowledged_by` REFERENCES `users(id)` ON DELETE RESTRICT.
* **Indexes:**
  * `ix_alert_acknowledgments_order_id` ON `order_id` — Lookup latest acknowledgment for an order.

---

## 4. Relationships and Cardinality

```text
users (1) ────< (N) orders                    [1:N via orders.primary_waiter_id]
users (1) ────< (N) order_collaborators       [M:N via junction order_collaborators]
orders (1) ───< (N) order_collaborators       [M:N via junction order_collaborators]
orders (1) ───< (N) order_lines               [1:N via order_lines.order_id]
menu_items (1) < (N) order_lines              [1:N via order_lines.menu_item_id]
orders (1) ───< (N) order_events              [1:N via order_events.order_id]
users (1) ────< (N) order_events              [1:N via order_events.user_id]
order_lines (1) < (N) order_events           [1:N (nullable) via order_events.order_line_id]
orders (1) ───< (N) alert_acknowledgments     [1:N via alert_acknowledgments.order_id]
users (1) ────< (N) alert_acknowledgments     [1:N via alert_acknowledgments.acknowledged_by]
```

### Relationship Cardinality Summary
1. `users` to `orders`: **One-to-Many** (Mandatory creator / primary waiter).
2. `users` to `orders` (Collaborators): **Many-to-Many** via `order_collaborators`.
3. `orders` to `order_lines`: **One-to-Many** (An order has 0 to N lines; an order line belongs to exactly 1 order).
4. `menu_items` to `order_lines`: **One-to-Many** (A menu item can appear across multiple order lines).
5. `orders` to `order_events`: **One-to-Many** (An order has 1 to N immutable timeline events).
6. `orders` to `alert_acknowledgments`: **One-to-Many** (An order has 0 to N acknowledgment records).

---

## 5. Enums and States

### 5.1. Order Lifecycle Statuses (`orders.status`)
* **Values:** `'placed'`, `'accepted'`, `'preparing'`, `'ready'`, `'served'`, `'cancelled'`
* **Lifecycle Rules:**
  * `placed` → `accepted` | `cancelled`
  * `accepted` → `preparing` | `cancelled`
  * `preparing` → `ready` (Cancellation is strictly forbidden once preparing has commenced)
  * `ready` → `served`
  * `served` → *Terminal state* (No further transitions or line modifications)
  * `cancelled` → *Terminal state* (No further transitions or line modifications)

### 5.2. User Roles (`users.role`)
* **Values:** `'manager'`, `'waiter'`

### 5.3. Audit Event Types (`order_events.event_type`)
* **Values:** `'status_change'`, `'line_added'`, `'line_voided'`, `'note_added'`

---

## 6. Detailed Domain Models & Analysis

### 6.1. Ingredient & Menu Availability Logic
* **Finding:** The scenario mentions running out of ingredients on a chalkboard, but ingredient-level inventory tracking is explicitly listed under `README.md` **Stretch ideas (optional)**: *"Ingredient-level stock deduction per order"*.
* **Decision:** No `ingredients`, `recipes`, or `inventory` tables are created in the core schema.
* **Mechanism:** Managed entirely via `menu_items.is_available` (boolean toggle) and `menu_items.is_archived` (boolean catalog retirement).
  * `is_available = FALSE` signifies an ingredient/dish is temporarily unavailable.
  * `is_archived = TRUE` permanently hides the dish from standard menus.

### 6.2. Orders & Historical Price Snapshot
* **Requirement:** Goal 3 states: *"Opening an order shows its lines and their running total, calculated by the server from the menu items' current prices at the time each line was added."*
* **Design Decision:** `order_lines.unit_price` stores the price snapshot at insertion.
* **Total Calculation:** `SUM(quantity * unit_price)` for all rows where `is_voided = FALSE`. If a menu item price changes later, historical orders and order lines retain the price snapshot recorded at addition time.

### 6.3. Users & Role-Based Permissions
* **Server-Enforced Access Control:**
  * **Manager:** Can perform all CRUD operations on `menu_items`, bulk menu edits, and see/act on all `orders`.
  * **Waiter:** Can create orders (auto-assigned as `primary_waiter_id`), modify their own orders, or modify orders where their `user_id` exists in `order_collaborators`. Cannot modify other waiters' orders, create menu items, or change menu prices.

### 6.4. Immutable Order History
* **Requirement:** Goal 9 mandates an unalterable timeline showing status transitions, lines added, lines voided with reasons, and notes.
* **Design Decision:** `order_events` is strictly append-only. The API and service layer expose no `UPDATE` or `DELETE` endpoints for this table.

### 6.5. Slow-Order Alert Model
* **Requirement:** Goal 10 requires orders open > X minutes without reaching `ready` to appear in alerts, support dismissal/acknowledgment, and reappear if unresolved after Y more minutes.
* **Design Decision:** Alerts are **computed dynamically** via SQL query against `orders` joined with the latest record in `alert_acknowledgments`. No transient alert queue table is stored, eliminating sync drift.

---

## 7. Database Constraints vs Application Validation

| Rule / Constraint | Enforced in Database | Enforced in Application | Rationale |
| :--- | :---: | :---: | :--- |
| Valid user role | ✅ `CHECK (role IN ('manager', 'waiter'))` | ✅ Pydantic schema validation | Prevents illegal roles at both boundary and storage. |
| Positive item price | ✅ `CHECK (price > 0)` | ✅ Pydantic validation (`gt=0`) | Financial sanity check. |
| Positive line quantity | ✅ `CHECK (quantity > 0)` | ✅ Pydantic validation (`gt=0`) | Order line sanity check. |
| Positive table number | ✅ `CHECK (table_number > 0)` | ✅ Pydantic validation (`gt=0`) | Table number validation. |
| Valid order status | ✅ `CHECK (status IN (...))` | ✅ Pydantic Enum | Prevents invalid status strings. |
| Void requires reason | ✅ `CHECK (is_voided = FALSE OR void_reason IS NOT NULL)` | ✅ Service layer validation | Ensures voided lines cannot be saved without an explanatory reason. |
| Unique collaborator | ✅ `UNIQUE (order_id, user_id)` | ✅ Service layer check | Prevents duplicate collaborator entries. |
| Order lifecycle progression | ❌ (Dynamic state machine) | ✅ Service layer state machine | Lifecycle checks require distinct error messages (e.g. "Cannot cancel once preparing"). |
| Order line addition allowed | ❌ (Dependent on order status) | ✅ Service layer check | Verifies order is not in `served` or `cancelled` state prior to line insertion. |
| Collaborator eligibility | ❌ (Query check) | ✅ Service layer check | Verifies added user is a waiter and not already the primary waiter. |

---

## 8. Indexing Strategy

1. `ix_users_email` ON `users(email)` — Fast authentication lookups.
2. `ix_users_role` ON `users(role)` — Filtering waiters for collaborator assignment.
3. `ix_menu_items_is_archived` ON `menu_items(is_archived)` — Filtering active menu catalog.
4. `ix_menu_items_is_available` ON `menu_items(is_available)` — Quick lookup for orderable dishes.
5. `ix_orders_status` ON `orders(status)` — Filtering by status and computing dashboard metrics.
6. `ix_orders_table_number` ON `orders(table_number)` — Searching orders by table number.
7. `ix_orders_created_at` ON `orders(created_at)` — Range filtering, 14-day charts, daily CSV export, sorting.
8. `ix_orders_primary_waiter_id` ON `orders(primary_waiter_id)` — Filtering orders by primary waiter.
9. `ix_orders_is_archived` ON `orders(is_archived)` — Active queue vs archived order segregation.
10. `ix_orders_status_created` ON `orders(status, created_at)` — Composite index for slow-order alert queries.
11. `ix_order_lines_order_id` ON `order_lines(order_id)` — Fetching lines for an order.
12. `ix_order_lines_menu_item_id` ON `order_lines(menu_item_id)` — Menu item reference queries.
13. `ix_order_collaborators_order_id` ON `order_collaborators(order_id)` — Fetching collaborator list for an order.
14. `ix_order_collaborators_user_id` ON `order_collaborators(user_id)` — Querying all orders a specific waiter collaborates on.
15. `ix_order_events_order_id` ON `order_events(order_id)` — Fetching audit timeline for an order.
16. `ix_order_events_created_at` ON `order_events(created_at)` — Chronological ordering of events.
17. `ix_alert_acknowledgments_order_id` ON `alert_acknowledgments(order_id)` — Finding latest acknowledgment for an order.

---

## 9. Deliberate Denormalization & 100x Scale Considerations

### Deliberate Denormalizations
* **`order_lines.unit_price`**: We store the exact price of the dish at the moment it was added to the order. This is a deliberate denormalization required by Goal 3 so that subsequent changes to `menu_items.price` do not alter the historical price or running total of past orders.

### What Would Break First at 100x Data Volume?
1. **Live Dashboard Aggregations (Goal 8):** Running live `SUM(unit_price * quantity)` and date-range groupings across millions of rows will increase query latency. **Solution at scale:** Implement continuous aggregates, materialized views refreshed concurrently, or summary tables updated via event triggers.
2. **Dynamic Slow-Order Alert Query (Goal 10):** Computing alert status by querying open orders and joining acknowledgments dynamically on every request will degrade under massive order volume. **Solution at scale:** The composite index `ix_orders_status_created` mitigates this for open orders. At high scale, a background queue (e.g. Celery / Redis / PostgreSQL LISTEN/NOTIFY) can maintain an in-memory alert index.
3. **Audit Timeline Table (`order_events`):** As the highest-volume table (recording multiple events per order), it will grow rapidly. **Solution at scale:** Range-partition `order_events` by `created_at` (e.g., monthly partitions) and implement cold storage archiving for historical records.

---

## 10. Seed and Demo Data Requirements

To demonstrate all 10 required goals upon initial deployment, the seed script must populate:
* **Users:**
  * 1 Manager (`manager@restaurant.com`)
  * 3 Waiters (`alice@restaurant.com`, `bob@restaurant.com`, `carol@restaurant.com`)
* **Menu Items (15 items):**
  * Active & available dishes (burgers, pizzas, salads, drinks, desserts)
  * Temporarily unavailable dishes (`is_available = FALSE`)
  * Retired/archived dishes (`is_archived = TRUE`)
* **Orders (12+ orders spanning all states):**
  * `placed` orders (including slow orders > 15 min old to demonstrate alerts)
  * `accepted` orders
  * `preparing` orders
  * `ready` orders
  * `served` orders with completed lines contributing to today's revenue
  * `cancelled` orders
  * Orders with collaborators assigned
  * Orders with voided lines and recorded void reasons
  * Orders with timeline notes
  * Archived orders (`is_archived = TRUE`)
* **14-Day Historical Orders:** Backdated served orders across the preceding 14 days to populate the Chart.js trendline.

---

## 11. Ambiguous Requirements & Decisions

| # | Ambiguity in Specification | Chosen Decision | Rationale |
| :--- | :--- | :--- | :--- |
| 1 | **Revenue Today definition** | Calculated as total from orders **served today** (`status = 'served'` and `updated_at >= today`). | Placed or in-flight orders have not yet concluded commercial transaction. |
| 2 | **Slow alert threshold values** | Configurable via environment: default `15 min` threshold, `10 min` reappear window. | Assignment specifies "a set number of minutes" without hardcoding numbers. |
| 3 | **CSV export permissions** | Restricted to **Manager** role. | Grouped under Goal 7 alongside manager-only bulk actions. |
| 4 | **Voided lines in running total** | Excluded from order total (`is_voided = FALSE`). | Customers are not charged for voided items. |
| 5 | **Table number uniqueness** | Multiple concurrent orders can use the same table number. | Accommodates separate checks or multiple seatings/courses. |

---

## 12. Requirements Coverage Audit

| Requirement / Goal | Database Entities Involved | Required Fields Covered | Relationships Covered | Status & Constraints Covered | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Accounts and Roles** | `users` | `id`, `name`, `email`, `password_hash`, `role` | 1:N with orders, events, alerts | Role check constraint, unique email | **COVERED** |
| **2. Orders** | `orders` | `id`, `table_number`, `status`, `primary_waiter_id`, `is_archived` | N:1 with `users`, 1:N with lines, events | Table number > 0, status check | **COVERED** |
| **3. Order Lines** | `order_lines` | `id`, `order_id`, `menu_item_id`, `quantity`, `special_instructions`, `unit_price` | N:1 with `orders`, N:1 with `menu_items` | Quantity > 0, unit_price > 0 | **COVERED** |
| **4. Lifecycle Rules** | `orders`, `order_lines`, `order_events` | `status`, `is_voided`, `void_reason` | Tracked in `order_events` | Check constraint on status, void reason required constraint | **COVERED** |
| **5. Collaborators** | `order_collaborators` | `id`, `order_id`, `user_id` | N:1 with `orders`, N:1 with `users` | Unique `(order_id, user_id)` constraint | **COVERED** |
| **6. Finding Orders** | `orders` | `table_number`, `status`, `primary_waiter_id`, `created_at` | Query joins with `users`, `collaborators` | 6 dedicated indexes for search, sort, filter, pagination | **COVERED** |
| **7. Bulk Menu & CSV** | `menu_items`, `orders`, `order_lines` | `price`, `is_available`, `is_archived` | Orders + lines query | Price > 0 constraint, CSV dynamically generated | **COVERED** |
| **8. Dashboard** | `orders`, `order_lines` | Aggregated columns | Live SQL joins and counts | Filter active / non-archived orders | **COVERED** |
| **9. Immutable History** | `order_events` | `id`, `order_id`, `user_id`, `event_type`, `old_status`, `new_status`, `order_line_id`, `details` | N:1 with `orders`, `users`, `order_lines` | Append-only event type check | **COVERED** |
| **10. Slow-Order Alerts** | `orders`, `alert_acknowledgments` | `order_id`, `acknowledged_by`, `acknowledged_at` | N:1 with `orders`, `users` | Threshold logic computed dynamically | **COVERED** |
