import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database.connection import engine


def test_connection():
    print("Testing Supabase PostgreSQL connectivity...")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1;"))
            value = result.scalar()
            if value == 1:
                print("SUCCESS: Database connection established successfully! (Query 'SELECT 1' returned 1)")
                return True
            else:
                print(f"FAILURE: Unexpected query result: {value}")
                return False
    except Exception as e:
        print(f"FAILURE: Database connection failed: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
