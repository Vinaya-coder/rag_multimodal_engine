import asyncio
import sqlalchemy
from sqlalchemy import text

# Update this with your actual database URL from your .env
DB_URL = "postgresql+psycopg2://postgres:vinaya@localhost:5432/multimodal_search"


async def check_database():
    engine = sqlalchemy.create_engine(DB_URL)
    with engine.connect() as conn:
        print("\n--- DATABASE CONTENT CHECK ---")
        # Fetch everything to see what is stored
        stmt = text("SELECT filename, description, start_time FROM media_vault LIMIT 50")
        result = conn.execute(stmt)

        rows = result.fetchall()
        if not rows:
            print("Database is empty!")
            return

        print(f"Found {len(rows)} items total.\n")
        print(f"{'FILENAME':<25} | {'START':<6} | {'DESCRIPTION'}")
        print("-" * 80)

        for row in rows:
            desc = (row[1][:50] + '...') if row[1] and len(row[1]) > 50 else row[1]
            print(f"{row[0]:<25} | {str(row[2]):<6} | {desc}")


if __name__ == "__main__":
    asyncio.run(check_database())