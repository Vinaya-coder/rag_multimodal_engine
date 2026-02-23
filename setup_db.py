from app.drivers.database import engine, Base
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup-db")


def init_db():
    try:
        with engine.connect() as conn:
            logger.info("Enabling pgvector extension...")
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

            # 2. Create tables
            logger.info("Creating tables in multimodal_search database...")
            # This looks at your sql_models.py and builds the media_vault table
            Base.metadata.create_all(bind=engine)

            logger.info("Database setup complete and verified.")

    except Exception as e:
        logger.error(f"Database setup failed: {e}")


if __name__ == "__main__":
    init_db()