import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from app.database.connection import engine


def verify_schema():
    print("==================================================")
    print("DATABASE STRUCTURE VERIFICATION (Supabase PostgreSQL)")
    print("==================================================")

    inspector = inspect(engine)
    
    # 1. Verify Tables
    expected_tables = {
        "users",
        "menu_items",
        "orders",
        "order_lines",
        "order_collaborators",
        "order_events",
        "alert_acknowledgments",
    }
    actual_tables = set(inspector.get_table_names(schema="public")) - {"alembic_version"}
    print(f"\n1. Tables in 'public' schema ({len(actual_tables)}):")
    for t in sorted(actual_tables):
        print(f"   - {t}")
    assert actual_tables == expected_tables, f"Table mismatch: {actual_tables} != {expected_tables}"
    print("   -> EXACT MATCH with required 7 tables!")

    # 2. Verify Primary Keys
    print("\n2. Primary Keys:")
    for t in sorted(expected_tables):
        pk = inspector.get_pk_constraint(t, schema="public")
        print(f"   - {t}: PK columns = {pk.get('constrained_columns')}")
        assert len(pk.get('constrained_columns', [])) == 1 and pk['constrained_columns'][0] == 'id', f"Invalid PK on {t}"

    # 3. Verify Foreign Keys
    print("\n3. Foreign Keys:")
    for t in sorted(expected_tables):
        fks = inspector.get_foreign_keys(t, schema="public")
        for fk in fks:
            print(f"   - {t}.{fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']} (ondelete={fk.get('options', {}).get('ondelete')})")

    # 4. Verify Unique Constraints
    print("\n4. Unique Constraints & Indexes:")
    for t in sorted(expected_tables):
        unique_cons = inspector.get_unique_constraints(t, schema="public")
        indexes = inspector.get_indexes(t, schema="public")
        print(f"   - {t}:")
        for uc in unique_cons:
            print(f"     * UNIQUE CONSTRAINT: {uc['name']} on {uc['column_names']}")
        for ix in indexes:
            print(f"     * INDEX: {ix['name']} on {ix['column_names']} (unique={ix['unique']})")

    # 5. Verify Check Constraints
    print("\n5. Check Constraints:")
    for t in sorted(expected_tables):
        check_cons = inspector.get_check_constraints(t, schema="public")
        print(f"   - {t}: {[c['name'] for c in check_cons]}")

    # 6. Verify Alembic Version
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        print(f"\n6. Current Alembic Revision in Database: {ver}")
        assert ver == "edd2eac79e58", f"Alembic revision mismatch: {ver} != edd2eac79e58"

    print("\n==================================================")
    print("ALL DATABASE STRUCTURE CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    verify_schema()
