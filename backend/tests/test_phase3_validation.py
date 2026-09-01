import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, select, func
from app.database.connection import SessionLocal, engine
from app.models import (
    User,
    MenuItem,
    Order,
    OrderLine,
    OrderCollaborator,
    OrderEvent,
    AlertAcknowledgment,
)


def validate_phase3():
    print("==================================================")
    print("PHASE 3 VERIFICATION: Migration & Seed Data")
    print("==================================================")

    db = SessionLocal()
    try:
        # 1. Check Alembic Revision in Database
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            print(f"1. Current Alembic Revision: {rev}")
            assert rev == "edd2eac79e58", f"Unexpected revision: {rev}"

        # 2. Verify Table Row Counts
        user_count = db.scalar(select(func.count(User.id)))
        menu_count = db.scalar(select(func.count(MenuItem.id)))
        order_count = db.scalar(select(func.count(Order.id)))
        line_count = db.scalar(select(func.count(OrderLine.id)))
        collab_count = db.scalar(select(func.count(OrderCollaborator.id)))
        event_count = db.scalar(select(func.count(OrderEvent.id)))
        ack_count = db.scalar(select(func.count(AlertAcknowledgment.id)))

        print("\n2. Database Table Row Counts:")
        print(f"   - users: {user_count}")
        print(f"   - menu_items: {menu_count}")
        print(f"   - orders: {order_count}")
        print(f"   - order_lines: {line_count}")
        print(f"   - order_collaborators: {collab_count}")
        print(f"   - order_events: {event_count}")
        print(f"   - alert_acknowledgments: {ack_count}")

        assert user_count == 4, f"Expected 4 users, found {user_count}"
        assert menu_count == 15, f"Expected 15 menu items, found {menu_count}"
        assert order_count >= 12, f"Expected at least 12 orders, found {order_count}"
        assert line_count >= 20, f"Expected at least 20 order lines, found {line_count}"
        assert collab_count >= 2, f"Expected at least 2 collaborators, found {collab_count}"
        assert event_count >= 12, f"Expected at least 12 events, found {event_count}"
        assert ack_count >= 1, f"Expected at least 1 acknowledgment, found {ack_count}"

        # 3. Verify Users by Role
        managers = db.scalars(select(User).where(User.role == "manager")).all()
        waiters = db.scalars(select(User).where(User.role == "waiter")).all()
        print(f"\n3. Users Verification:")
        print(f"   - Managers ({len(managers)}): {[m.name for m in managers]}")
        print(f"   - Waiters ({len(waiters)}): {[w.name for w in waiters]}")
        assert len(managers) == 1, "Must have 1 manager"
        assert len(waiters) == 3, "Must have 3 waiters"

        # 4. Verify Menu Items by Availability & Archive State
        avail_count = db.scalar(select(func.count(MenuItem.id)).where(MenuItem.is_available.is_(True), MenuItem.is_archived.is_(False)))
        unavail_count = db.scalar(select(func.count(MenuItem.id)).where(MenuItem.is_available.is_(False), MenuItem.is_archived.is_(False)))
        archived_count = db.scalar(select(func.count(MenuItem.id)).where(MenuItem.is_archived.is_(True)))
        print(f"\n4. Menu Items Breakdown:")
        print(f"   - Available active dishes: {avail_count}")
        print(f"   - Unavailable dishes: {unavail_count}")
        print(f"   - Archived dishes: {archived_count}")
        assert avail_count == 12, "Expected 12 available dishes"
        assert unavail_count == 2, "Expected 2 unavailable dishes"
        assert archived_count == 1, "Expected 1 archived dish"

        # 5. Verify Orders Lifecycle Distribution
        statuses = db.execute(text("SELECT status, count(*) FROM orders GROUP BY status ORDER BY status;")).fetchall()
        print(f"\n5. Orders by Lifecycle Status:")
        status_map = {}
        for s, c in statuses:
            print(f"   - {s}: {c}")
            status_map[s] = c
        for expected_status in ['placed', 'accepted', 'preparing', 'ready', 'served', 'cancelled']:
            assert expected_status in status_map, f"Missing order status {expected_status}"

        # 6. Verify Foreign Key Referential Integrity (No Orphaned Records)
        with engine.connect() as conn:
            orphaned_orders = conn.execute(text("SELECT count(*) FROM orders o LEFT JOIN users u ON o.primary_waiter_id = u.id WHERE u.id IS NULL;")).scalar()
            orphaned_lines_order = conn.execute(text("SELECT count(*) FROM order_lines ol LEFT JOIN orders o ON ol.order_id = o.id WHERE o.id IS NULL;")).scalar()
            orphaned_lines_menu = conn.execute(text("SELECT count(*) FROM order_lines ol LEFT JOIN menu_items m ON ol.menu_item_id = m.id WHERE m.id IS NULL;")).scalar()
            orphaned_collab_order = conn.execute(text("SELECT count(*) FROM order_collaborators oc LEFT JOIN orders o ON oc.order_id = o.id WHERE o.id IS NULL;")).scalar()
            orphaned_collab_user = conn.execute(text("SELECT count(*) FROM order_collaborators oc LEFT JOIN users u ON oc.user_id = u.id WHERE u.id IS NULL;")).scalar()
            orphaned_events = conn.execute(text("SELECT count(*) FROM order_events oe LEFT JOIN orders o ON oe.order_id = o.id WHERE o.id IS NULL;")).scalar()
            orphaned_acks = conn.execute(text("SELECT count(*) FROM alert_acknowledgments aa LEFT JOIN orders o ON aa.order_id = o.id WHERE o.id IS NULL;")).scalar()

            assert orphaned_orders == 0
            assert orphaned_lines_order == 0
            assert orphaned_lines_menu == 0
            assert orphaned_collab_order == 0
            assert orphaned_collab_user == 0
            assert orphaned_events == 0
            assert orphaned_acks == 0
            print("\n6. Referential Integrity Check:")
            print("   -> 0 orphaned records across all tables (100% Valid Foreign Keys)")

        # 7. Check Voided Lines have Reasons
        voided_without_reason = db.scalar(
            select(func.count(OrderLine.id)).where(
                OrderLine.is_voided.is_(True),
                (OrderLine.void_reason.is_(None)) | (func.length(func.trim(OrderLine.void_reason)) == 0)
            )
        )
        assert voided_without_reason == 0, "Found voided lines without reason"
        print("\n7. Voided Lines Check:")
        print("   -> All voided lines have explanatory reasons as required by Goal 4.")

    finally:
        db.close()

    print("\n==================================================")
    print("ALL PHASE 3 VERIFICATION CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    validate_phase3()
