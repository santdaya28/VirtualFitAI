import os
import logging
from pathlib import Path
from typing import Generator, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

# Load environment variables from backend/.env regardless of execution directory
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

logger = logging.getLogger("virtualfit.database")

# Declarative Base for SQLAlchemy ORM models
class Base(DeclarativeBase):
    pass

# Retrieve database connection string from environment variables
# Never hardcode passwords or connection credentials in code
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None

# Handle missing or configured DATABASE_URL gracefully
if not DATABASE_URL:
    logger.warning(
        "DATABASE_URL is not set in environment. "
        "Database connectivity will be disabled and backend will operate in standalone mode."
    )
else:
    # Ensure correct psycopg (v3) dialect prefix if standard postgresql:// is provided
    db_url = DATABASE_URL
    if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        engine = create_engine(
            db_url,
            pool_pre_ping=True,  # Automatically detects stale/dropped connections
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 3},
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("SQLAlchemy database engine and sessionmaker initialized successfully.")
    except Exception as exc:
        logger.error(f"Failed to create SQLAlchemy engine with provided DATABASE_URL: {exc}")
        engine = None
        SessionLocal = None

def get_db() -> Generator[Optional[Session], None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session per request.
    Yields None gracefully if the database engine is not initialized.
    """
    if SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health() -> dict:
    """
    Health check utility to verify PostgreSQL connectivity.
    Returns status: 'connected', 'disconnected', or 'unconfigured'.
    """
    if not DATABASE_URL:
        return {
            "status": "unconfigured",
            "message": "DATABASE_URL is not set in environment",
        }

    if engine is None:
        return {
            "status": "error",
            "message": "Database engine failed to initialize",
        }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return {
                "status": "connected",
                "database": "PostgreSQL",
                "message": "Database connection is healthy and responsive",
            }
    except Exception as exc:
        return {
            "status": "disconnected",
            "database": "PostgreSQL",
            "message": f"Database unreachable on specified port/host: {exc}",
        }
