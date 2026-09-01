import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database.connection import engine
from app.models import (
    Base,
    User,
    MenuItem,
    Order,
    OrderLine,
    OrderCollaborator,
    OrderEvent,
    AlertAcknowledgment,
)


def validate_phase2():
    print("========================================")
    print("PHASE 2 VALIDATION: Models & Migrations")
    print("========================================")

    # 1. Models & Metadata
    expected_models = [
        User,
        MenuItem,
        Order,
        OrderLine,
        OrderCollaborator,
        OrderEvent,
        AlertAcknowledgment,
    ]
    print(f"1. Verified {len(expected_models)} model classes defined.")

    expected_tables = {
        "users",
        "menu_items",
        "orders",
        "order_lines",
        "order_collaborators",
        "order_events",
        "alert_acknowledgments",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert registered_tables == expected_tables, f"Mismatch in tables: {registered_tables} != {expected_tables}"
    print(f"2. SQLAlchemy Base.metadata contains exactly the 7 required tables:")
    for t in sorted(registered_tables):
        print(f"   - {t}")

    # 2. Database Connectivity
    print("\n3. Testing live database connectivity with SELECT 1...")
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1;")).scalar()
        assert res == 1, "SELECT 1 did not return 1"
        print("   -> SELECT 1 returned 1 (SUCCESS)")

        # 3. Verify Supabase has NOT been modified
        print("\n4. Verifying Supabase schema state...")
        query = text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
        )
        existing_tables = [row[0] for row in conn.execute(query).fetchall()]
        print(f"   -> Tables currently in Supabase 'public' schema: {existing_tables}")
        for app_table in expected_tables:
            assert app_table not in existing_tables, f"Table '{app_table}' was found in database!"
        print("   -> CONFIRMED: Supabase database has NOT been modified. No tables created yet.")

    print("\n========================================")
    print("ALL PHASE 2 VALIDATION CHECKS PASSED!")
    print("========================================")


if __name__ == "__main__":
    validate_phase2()
