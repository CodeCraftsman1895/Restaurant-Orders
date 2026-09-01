import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database.connection import engine


def inspect_db():
    with engine.connect() as conn:
        q = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;")
        tables = [r[0] for r in conn.execute(q).fetchall()]
        print("Existing tables in Supabase 'public':", tables)


if __name__ == "__main__":
    inspect_db()
