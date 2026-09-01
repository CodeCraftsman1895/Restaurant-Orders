import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import bcrypt

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models import (
    User,
    MenuItem,
    Order,
    OrderLine,
    OrderCollaborator,
    OrderEvent,
    AlertAcknowledgment,
)

NAMESPACE_SEED = uuid.UUID("a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d")


def deterministic_uuid(key: str) -> uuid.UUID:
    """Generate a stable, repeatable UUID based on a unique key string."""
    return uuid.uuid5(NAMESPACE_SEED, key)


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_database(db: Session) -> dict:
    """
    Idempotently seeds the database with demo users, menu items, orders,
    collaborators, order lines, audit events, and alert acknowledgments.
    """
    now = datetime.now(timezone.utc)
    stats = {"created": {}, "updated": {}, "skipped": {}}

    # =========================================================================
    # 1. USERS (1 Manager, 3 Waiters)
    # =========================================================================
    users_data = [
        {
            "key": "user:manager@restaurant.com",
            "name": "Sarah Manager",
            "email": "manager@restaurant.com",
            "password": "manager123",
            "role": "manager",
        },
        {
            "key": "user:alice@restaurant.com",
            "name": "Alice Johnson",
            "email": "alice@restaurant.com",
            "password": "waiter123",
            "role": "waiter",
        },
        {
            "key": "user:bob@restaurant.com",
            "name": "Bob Smith",
            "email": "bob@restaurant.com",
            "password": "waiter123",
            "role": "waiter",
        },
        {
            "key": "user:carol@restaurant.com",
            "name": "Carol Davis",
            "email": "carol@restaurant.com",
            "password": "waiter123",
            "role": "waiter",
        },
    ]

    user_map = {}
    for u in users_data:
        user_id = deterministic_uuid(u["key"])
        existing = db.get(User, user_id)
        if not existing:
            user_obj = User(
                id=user_id,
                name=u["name"],
                email=u["email"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
                created_at=now - timedelta(days=30),
                updated_at=now - timedelta(days=30),
            )
            db.add(user_obj)
            stats["created"]["users"] = stats["created"].get("users", 0) + 1
            user_map[u["email"]] = user_obj
        else:
            existing.name = u["name"]
            existing.role = u["role"]
            stats["updated"]["users"] = stats["updated"].get("users", 0) + 1
            user_map[u["email"]] = existing

    db.flush()

    # =========================================================================
    # 2. MENU ITEMS (15 dishes: 12 available, 2 unavailable, 1 archived)
    # =========================================================================
    menu_data = [
        {"name": "Classic Burger", "price": Decimal("12.99"), "is_available": True, "is_archived": False},
        {"name": "Cheeseburger Deluxe", "price": Decimal("14.99"), "is_available": True, "is_archived": False},
        {"name": "Grilled Chicken Sandwich", "price": Decimal("13.49"), "is_available": True, "is_archived": False},
        {"name": "Caesar Salad", "price": Decimal("10.99"), "is_available": True, "is_archived": False},
        {"name": "Fish and Chips", "price": Decimal("15.99"), "is_available": True, "is_archived": False},
        {"name": "Margherita Pizza", "price": Decimal("13.99"), "is_available": True, "is_archived": False},
        {"name": "Pasta Carbonara", "price": Decimal("14.49"), "is_available": True, "is_archived": False},
        {"name": "Tomato Soup", "price": Decimal("7.99"), "is_available": True, "is_archived": False},
        {"name": "Garlic Bread", "price": Decimal("5.99"), "is_available": True, "is_archived": False},
        {"name": "French Fries", "price": Decimal("4.99"), "is_available": True, "is_archived": False},
        {"name": "Chocolate Cake", "price": Decimal("8.99"), "is_available": True, "is_archived": False},
        {"name": "Ice Cream Sundae", "price": Decimal("6.99"), "is_available": True, "is_archived": False},
        {"name": "Lobster Tail", "price": Decimal("29.99"), "is_available": False, "is_archived": False},
        {"name": "Truffle Risotto", "price": Decimal("24.99"), "is_available": False, "is_archived": False},
        {"name": "Seasonal Special Platter", "price": Decimal("19.99"), "is_available": False, "is_archived": True},
    ]

    menu_map = {}
    for m in menu_data:
        item_id = deterministic_uuid(f"menu:{m['name']}")
        existing = db.get(MenuItem, item_id)
        if not existing:
            item_obj = MenuItem(
                id=item_id,
                name=m["name"],
                price=m["price"],
                is_available=m["is_available"],
                is_archived=m["is_archived"],
                created_at=now - timedelta(days=20),
                updated_at=now - timedelta(days=20),
            )
            db.add(item_obj)
            stats["created"]["menu_items"] = stats["created"].get("menu_items", 0) + 1
            menu_map[m["name"]] = item_obj
        else:
            existing.price = m["price"]
            existing.is_available = m["is_available"]
            existing.is_archived = m["is_archived"]
            stats["updated"]["menu_items"] = stats["updated"].get("menu_items", 0) + 1
            menu_map[m["name"]] = existing

    db.flush()

    # =========================================================================
    # 3. CORE DEMO ORDERS (12 Orders covering all lifecycle states & workflows)
    # =========================================================================
    demo_orders = [
        # Order 1: Slow order (placed 25m ago, ack'd 5m ago by Alice)
        {
            "code": "demo_order_1",
            "table": 1,
            "status": "placed",
            "waiter": "alice@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=25),
            "updated_at": now - timedelta(minutes=25),
            "lines": [
                {"item": "Classic Burger", "qty": 2, "notes": "No onions on one", "voided": False},
                {"item": "French Fries", "qty": 2, "notes": "Extra crispy", "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [{"by": "alice@restaurant.com", "at": now - timedelta(minutes=5)}],
            "notes": [],
        },
        # Order 2: Slow order (accepted 20m ago, unacknowledged)
        {
            "code": "demo_order_2",
            "table": 2,
            "status": "accepted",
            "waiter": "alice@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=20),
            "updated_at": now - timedelta(minutes=18),
            "lines": [
                {"item": "Margherita Pizza", "qty": 1, "notes": "Extra basil", "voided": False},
                {"item": "Caesar Salad", "qty": 1, "notes": "Dressing on the side", "voided": False},
                {"item": "Garlic Bread", "qty": 1, "notes": None, "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 3: Active Preparing order (10m ago)
        {
            "code": "demo_order_3",
            "table": 3,
            "status": "preparing",
            "waiter": "bob@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=10),
            "updated_at": now - timedelta(minutes=7),
            "lines": [
                {"item": "Pasta Carbonara", "qty": 2, "notes": "Extra parmesan", "voided": False},
                {"item": "Tomato Soup", "qty": 2, "notes": "Hot", "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 4: Ready for pickup (15m ago)
        {
            "code": "demo_order_4",
            "table": 4,
            "status": "ready",
            "waiter": "bob@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=15),
            "updated_at": now - timedelta(minutes=2),
            "lines": [
                {"item": "Fish and Chips", "qty": 1, "notes": "Extra tartar sauce", "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 5: Served today (with a voided line and a note) -> contributes to revenue today
        {
            "code": "demo_order_5",
            "table": 5,
            "status": "served",
            "waiter": "carol@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(minutes=45),
            "lines": [
                {"item": "Cheeseburger Deluxe", "qty": 2, "notes": "Medium rare", "voided": False},
                {"item": "Garlic Bread", "qty": 1, "notes": None, "voided": True, "reason": "Sent wrong item to table"},
                {"item": "Chocolate Cake", "qty": 2, "notes": "Warm with cream", "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": ["Guest requested booth seating away from entrance"],
        },
        # Order 6: Served today -> contributes to revenue today
        {
            "code": "demo_order_6",
            "table": 6,
            "status": "served",
            "waiter": "alice@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(hours=3),
            "updated_at": now - timedelta(hours=1, minutes=30),
            "lines": [
                {"item": "Grilled Chicken Sandwich", "qty": 2, "notes": None, "voided": False},
                {"item": "Ice Cream Sundae", "qty": 2, "notes": "Chocolate syrup", "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 7: Cancelled order (with voided line)
        {
            "code": "demo_order_7",
            "table": 7,
            "status": "cancelled",
            "waiter": "bob@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(hours=4),
            "updated_at": now - timedelta(hours=3, minutes=50),
            "lines": [
                {"item": "Cheeseburger Deluxe", "qty": 1, "notes": None, "voided": True, "reason": "Customer changed mind before kitchen started"},
                {"item": "French Fries", "qty": 1, "notes": None, "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": ["Customer had to leave unexpectedly"],
        },
        # Order 8: Slow order placed 35m ago (never acknowledged)
        {
            "code": "demo_order_8",
            "table": 8,
            "status": "placed",
            "waiter": "carol@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=35),
            "updated_at": now - timedelta(minutes=35),
            "lines": [
                {"item": "Margherita Pizza", "qty": 2, "notes": None, "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 9: Archived order from yesterday
        {
            "code": "demo_order_9",
            "table": 9,
            "status": "served",
            "waiter": "alice@restaurant.com",
            "is_archived": True,
            "created_at": now - timedelta(days=1, hours=2),
            "updated_at": now - timedelta(days=1, hours=1),
            "lines": [
                {"item": "Classic Burger", "qty": 3, "notes": None, "voided": False},
                {"item": "French Fries", "qty": 3, "notes": None, "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 10: Archived order from 3 days ago
        {
            "code": "demo_order_10",
            "table": 10,
            "status": "served",
            "waiter": "bob@restaurant.com",
            "is_archived": True,
            "created_at": now - timedelta(days=3, hours=4),
            "updated_at": now - timedelta(days=3, hours=3),
            "lines": [
                {"item": "Pasta Carbonara", "qty": 2, "notes": None, "voided": False},
                {"item": "Caesar Salad", "qty": 1, "notes": None, "voided": False},
            ],
            "collaborators": [],
            "acknowledgments": [],
            "notes": [],
        },
        # Order 11: Preparing order with Collaborator (Carol primary, Alice collaborating)
        {
            "code": "demo_order_11",
            "table": 11,
            "status": "preparing",
            "waiter": "carol@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=8),
            "updated_at": now - timedelta(minutes=4),
            "lines": [
                {"item": "Fish and Chips", "qty": 2, "notes": "Vinegar on the side", "voided": False},
                {"item": "Tomato Soup", "qty": 1, "notes": None, "voided": False},
            ],
            "collaborators": ["alice@restaurant.com"],
            "acknowledgments": [],
            "notes": ["Allergy alert: Table requested separate fryers for gluten sensitivity"],
        },
        # Order 12: Accepted order with Collaborator (Alice primary, Bob collaborating)
        {
            "code": "demo_order_12",
            "table": 12,
            "status": "accepted",
            "waiter": "alice@restaurant.com",
            "is_archived": False,
            "created_at": now - timedelta(minutes=5),
            "updated_at": now - timedelta(minutes=3),
            "lines": [
                {"item": "Classic Burger", "qty": 1, "notes": "Well done", "voided": False},
                {"item": "Chocolate Cake", "qty": 1, "notes": None, "voided": False},
            ],
            "collaborators": ["bob@restaurant.com"],
            "acknowledgments": [],
            "notes": [],
        },
    ]

    # Process Core Orders
    for o in demo_orders:
        order_id = deterministic_uuid(f"order:{o['code']}")
        primary_waiter = user_map[o["waiter"]]

        order_obj = db.get(Order, order_id)
        if not order_obj:
            order_obj = Order(
                id=order_id,
                table_number=o["table"],
                status=o["status"],
                primary_waiter_id=primary_waiter.id,
                is_archived=o["is_archived"],
                created_at=o["created_at"],
                updated_at=o["updated_at"],
            )
            db.add(order_obj)
            stats["created"]["orders"] = stats["created"].get("orders", 0) + 1
        else:
            order_obj.status = o["status"]
            order_obj.is_archived = o["is_archived"]
            order_obj.updated_at = o["updated_at"]
            stats["updated"]["orders"] = stats["updated"].get("orders", 0) + 1

        db.flush()

        # Collaborators
        for c_email in o["collaborators"]:
            c_user = user_map[c_email]
            collab_id = deterministic_uuid(f"collab:{order_id}:{c_user.id}")
            if not db.get(OrderCollaborator, collab_id):
                collab_obj = OrderCollaborator(
                    id=collab_id,
                    order_id=order_id,
                    user_id=c_user.id,
                    created_at=o["created_at"],
                )
                db.add(collab_obj)
                stats["created"]["order_collaborators"] = stats["created"].get("order_collaborators", 0) + 1

        # Order Lines
        for idx, line_info in enumerate(o["lines"]):
            line_id = deterministic_uuid(f"line:{order_id}:{idx}")
            menu_item = menu_map[line_info["item"]]
            existing_line = db.get(OrderLine, line_id)
            if not existing_line:
                line_obj = OrderLine(
                    id=line_id,
                    order_id=order_id,
                    menu_item_id=menu_item.id,
                    quantity=line_info["qty"],
                    special_instructions=line_info.get("notes"),
                    unit_price=menu_item.price,
                    is_voided=line_info["voided"],
                    void_reason=line_info.get("reason"),
                    created_at=o["created_at"] + timedelta(seconds=idx * 10),
                )
                db.add(line_obj)
                stats["created"]["order_lines"] = stats["created"].get("order_lines", 0) + 1

                # Line added event
                evt_id = deterministic_uuid(f"event:line_added:{line_id}")
                if not db.get(OrderEvent, evt_id):
                    evt = OrderEvent(
                        id=evt_id,
                        order_id=order_id,
                        user_id=primary_waiter.id,
                        event_type="line_added",
                        order_line_id=line_id,
                        details=f"Added {line_info['qty']}x {menu_item.name}",
                        created_at=line_obj.created_at,
                    )
                    db.add(evt)
                    stats["created"]["order_events"] = stats["created"].get("order_events", 0) + 1

                # Line voided event if applicable
                if line_info["voided"]:
                    void_evt_id = deterministic_uuid(f"event:line_voided:{line_id}")
                    if not db.get(OrderEvent, void_evt_id):
                        void_evt = OrderEvent(
                            id=void_evt_id,
                            order_id=order_id,
                            user_id=primary_waiter.id,
                            event_type="line_voided",
                            order_line_id=line_id,
                            details=line_info.get("reason"),
                            created_at=o["updated_at"],
                        )
                        db.add(void_evt)
                        stats["created"]["order_events"] = stats["created"].get("order_events", 0) + 1

        # Notes
        for n_idx, note_text in enumerate(o["notes"]):
            note_evt_id = deterministic_uuid(f"event:note:{order_id}:{n_idx}")
            if not db.get(OrderEvent, note_evt_id):
                note_evt = OrderEvent(
                    id=note_evt_id,
                    order_id=order_id,
                    user_id=primary_waiter.id,
                    event_type="note_added",
                    details=note_text,
                    created_at=o["created_at"] + timedelta(minutes=1),
                )
                db.add(note_evt)
                stats["created"]["order_events"] = stats["created"].get("order_events", 0) + 1

        # Status change event
        status_evt_id = deterministic_uuid(f"event:status_initial:{order_id}")
        if not db.get(OrderEvent, status_evt_id):
            status_evt = OrderEvent(
                id=status_evt_id,
                order_id=order_id,
                user_id=primary_waiter.id,
                event_type="status_change",
                old_status=None,
                new_status="placed",
                created_at=o["created_at"],
            )
            db.add(status_evt)
            stats["created"]["order_events"] = stats["created"].get("order_events", 0) + 1

        if o["status"] != "placed":
            trans_evt_id = deterministic_uuid(f"event:status_final:{order_id}")
            if not db.get(OrderEvent, trans_evt_id):
                trans_evt = OrderEvent(
                    id=trans_evt_id,
                    order_id=order_id,
                    user_id=primary_waiter.id,
                    event_type="status_change",
                    old_status="placed",
                    new_status=o["status"],
                    created_at=o["updated_at"],
                )
                db.add(trans_evt)
                stats["created"]["order_events"] = stats["created"].get("order_events", 0) + 1

        # Alert Acknowledgments
        for a_idx, ack_info in enumerate(o["acknowledgments"]):
            ack_user = user_map[ack_info["by"]]
            ack_id = deterministic_uuid(f"ack:{order_id}:{a_idx}")
            if not db.get(AlertAcknowledgment, ack_id):
                ack_obj = AlertAcknowledgment(
                    id=ack_id,
                    order_id=order_id,
                    acknowledged_by=ack_user.id,
                    acknowledged_at=ack_info["at"],
                )
                db.add(ack_obj)
                stats["created"]["alert_acknowledgments"] = stats["created"].get("alert_acknowledgments", 0) + 1

    db.flush()

    # =========================================================================
    # 4. HISTORICAL SERVED ORDERS (14-Day Dashboard Chart.js trend data)
    # =========================================================================
    # Distribution of orders across days 1 to 13 ago
    history_counts = [3, 2, 4, 1, 3, 2, 5, 2, 3, 1, 4, 2, 3]
    waiter_list = ["alice@restaurant.com", "bob@restaurant.com", "carol@restaurant.com"]
    menu_sample = [
        "Classic Burger", "Margherita Pizza", "Pasta Carbonara",
        "Caesar Salad", "Fish and Chips", "French Fries"
    ]

    for day_offset, count in enumerate(history_counts, start=1):
        for o_idx in range(count):
            h_code = f"hist_day_{day_offset}_order_{o_idx}"
            h_order_id = deterministic_uuid(f"order:{h_code}")
            w_email = waiter_list[(day_offset + o_idx) % len(waiter_list)]
            waiter_user = user_map[w_email]
            order_time = now - timedelta(days=day_offset, hours=2 + o_idx, minutes=15)
            served_time = order_time + timedelta(minutes=25)

            h_order = db.get(Order, h_order_id)
            if not h_order:
                h_order = Order(
                    id=h_order_id,
                    table_number=10 + (o_idx % 8),
                    status="served",
                    primary_waiter_id=waiter_user.id,
                    is_archived=False,
                    created_at=order_time,
                    updated_at=served_time,
                )
                db.add(h_order)
                stats["created"]["orders"] = stats["created"].get("orders", 0) + 1
            db.flush()

            # Add 2 lines per historical order
            for l_idx in range(2):
                h_line_id = deterministic_uuid(f"line:{h_order_id}:{l_idx}")
                item_name = menu_sample[(day_offset + o_idx + l_idx) % len(menu_sample)]
                menu_item = menu_map[item_name]
                if not db.get(OrderLine, h_line_id):
                    h_line = OrderLine(
                        id=h_line_id,
                        order_id=h_order_id,
                        menu_item_id=menu_item.id,
                        quantity=1,
                        special_instructions=None,
                        unit_price=menu_item.price,
                        is_voided=False,
                        void_reason=None,
                        created_at=order_time,
                    )
                    db.add(h_line)
                    stats["created"]["order_lines"] = stats["created"].get("order_lines", 0) + 1

    db.commit()
    return stats


def main():
    print("==================================================")
    print("SEED DATA EXECUTION (Supabase PostgreSQL)")
    print("==================================================")
    db = SessionLocal()
    try:
        stats = seed_database(db)
        print("Seed execution finished successfully.")
        print("Summary of actions:")
        print("  Created:", stats["created"])
        print("  Updated:", stats["updated"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
