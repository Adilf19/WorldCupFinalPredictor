from database.connection import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print(result.fetchone()[0])
        print("✅ Connected successfully!")

except Exception as e:
    print(e)