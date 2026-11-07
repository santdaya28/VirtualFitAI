import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)

# Base class for all SQLAlchemy ORM models
class Base(DeclarativeBase):
    pass

# Create SQLAlchemy synchronous engine using psycopg3
# Set pool_pre_ping=True to automatically detect disconnected connections
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.warning(f"Database engine initialization warning: {e}")
    engine = None
    SessionLocal = None

def get_db():
    """
    FastAPI dependency yielding a database session per request
    """
    if SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> dict:
    """
    Safe test to verify whether the PostgreSQL database is reachable
    """
    if engine is None:
        return {
            "status": "unconfigured",
            "message": "SQLAlchemy engine not initialized",
        }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return {
                "status": "connected",
                "database": "PostgreSQL 18",
                "message": "Connection healthy",
            }
    except Exception as exc:
        return {
            "status": "disconnected",
            "database": "PostgreSQL (port 5432 stopped or unreachable)",
            "message": str(exc),
        }

