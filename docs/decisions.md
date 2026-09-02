# Decisions

Log of architectural and engineering decisions that shaped this codebase — documenting alternatives evaluated, trade-offs weighed, choices made, and one decision subsequently reversed.

---

## Decision 1: 7-Table Relational Schema vs. Inventory & Recipe Tables

- **Chose:** A focused 7-table relational schema (`users`, `menu_items`, `orders`, `order_lines`, `order_collaborators`, `order_events`, `alert_acknowledgments`) with dish availability managed via a boolean toggle `menu_items.is_available`.
- **Rejected:** Creating additional tables for `ingredients`, `recipes`, `inventory_batches`, and automatic ingredient deduction.
- **Why:** The scenario notes running out of ingredients on a chalkboard, but ingredient-level inventory tracking is explicitly listed under `README.md` **Stretch ideas (optional)**. Adding inventory tables would introduce unnecessary schema complexity, circular foreign keys, and transaction locking overhead during rush hours without contributing to the 10 core goals.
- **Consequences:** Kitchen availability is handled cleanly and instantly by managers toggling `is_available = FALSE`, which immediately blocks unavailable items from being added to orders across the dining room.

---

## Decision 2: Storing Price Snapshots on `order_lines.unit_price` vs. Dynamic Price Lookup

- **Chose:** Capturing and storing the dish price permanently on `order_lines.unit_price` at the moment an item is added to an order (deliberate denormalization).
- **Rejected:** Looking up the price dynamically from `menu_items.price` whenever viewing an order or calculating running totals.
- **Why:** In restaurant and financial POS systems, an order is an immutable commercial transaction. If a customer orders a $15 pasta on Monday, and on Wednesday the manager raises the menu price to $18, Monday's past receipts and accounting reports must remain exactly $15. Dynamic lookup would corrupt historical revenue and overcharge customers.
- **Consequences:** Past customer bills and accounting reports remain 100% stable and accurate regardless of future menu price adjustments.

---

## Decision 3: Dynamic SQL Evaluation for Slow-Order Alerts vs. Background Cron Queue Table

- **Chose:** Evaluating slow-order alerts dynamically via an indexed SQL query joining open orders against `alert_acknowledgments` with a composite index `(status, created_at)`.
- **Rejected:** Running a background worker (e.g., Celery/APScheduler) that constantly updates a dedicated `active_alerts` table.
- **Why:** A background polling worker introduces state desynchronization edge cases (e.g., worker delays, race conditions when an order is served just as an alert triggers, orphaned alert records). Dynamic SQL querying guarantees real-time accuracy: as soon as an order is marked `ready` or `served`, it instantly vanishes from alerts without needing a cleanup worker.
- **Consequences:** Eliminates external queue infrastructure (Redis/Celery) on free-tier hosting. The composite index `ix_orders_status_created` keeps queries sub-millisecond.

---

## Decision 4: Vanilla HTML5/CSS3/JavaScript & Chart.js vs. React/Next.js Framework

- **Chose:** Modern Vanilla JavaScript (ES6+), semantic HTML5, custom CSS3 design system, and Chart.js via CDN.
- **Rejected:** React, Next.js, Vue, or Angular SPA frameworks with Node.js build pipelines.
- **Why:** The assignment explicitly emphasizes that any stack is acceptable and warns against time spent wrestling with build tools over completing the 10 core goals. Vanilla JS eliminates npm build steps, hydration bugs, large bundle sizes, and separate frontend hosting configuration. The entire application is served directly and instantly by FastAPI.
- **Consequences:** Zero build time, instant page loads, easy local testing without Node.js installed, and clean separation between frontend presentation and backend REST APIs.

---

## Decision 5: Revenue Today Metric Calculation Basis

- **Chose:** Calculating today's revenue as the sum of non-voided line item snapshots (`quantity * unit_price`) on orders with `status == 'served'` that concluded today.
- **Rejected:** Summing all orders *placed* today regardless of their current status (`placed`, `accepted`, `preparing`).
- **Why (Later Reversed):**
  * **Later reversed:** In our initial Phase 7 implementation, order totals were accumulated as soon as orders were placed. During Phase 9 dashboard verification, we realized that orders in `placed`, `accepted`, or `preparing` status can still be modified, voided, or cancelled. In accounting practice, revenue is only realized once goods or services are delivered (`served`). We reversed the calculation to filter strictly on `orders.status = 'served'` and `orders.updated_at >= today_start`.
- **Consequences:** Today's revenue metric on the manager dashboard reflects true commercial receipts, entirely excluding cancelled orders and in-flight kitchen tickets.
