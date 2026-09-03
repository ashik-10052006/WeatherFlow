import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.config import settings

logger = logging.getLogger("weatherdata.database")

# Create engine with connection pooling and fast_executemany for SQL Server performance
engine = create_engine(
    settings.sqlalchemy_database_uri,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    fast_executemany=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> dict:
    """Verify database connectivity and return SQL Server version details."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT @@VERSION AS [version], DB_NAME() AS [current_db]"))
            row = result.fetchone()
            if row:
                return {
                    "connected": True,
                    "database": row[1],
                    "server_version": row[0].split("\n")[0].strip(),
                }
            return {"connected": True, "database": settings.db_database}
    except Exception as e:
        logger.error(f"Failed to connect to SQL Server: {e}")
        return {
            "connected": False,
            "error": str(e),
            "database": settings.db_database,
        }
