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

def init_db() -> bool:
    """
    Safely creates database tables for all registered models if they do not already exist.
    Will not drop or overwrite existing tables or data.
    Also ensures schema alignment for existing tables (e.g. adding missing columns).
    """
    # Import models here to ensure they are registered with Base.metadata
    import app.models  # noqa: F401

    if engine is None:
        logger.warning("Cannot initialize database tables: engine is not configured.")
        return False

    try:
        Base.metadata.create_all(bind=engine)

        # Non-destructive schema alignment for PostgreSQL
        if engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                conn.execute(text("""
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES products(id) ON DELETE SET NULL;
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS progress_percentage INTEGER NOT NULL DEFAULT 0;
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS stage_message VARCHAR(255);
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS provenance VARCHAR(50) NOT NULL DEFAULT 'mock_simulation';
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS error_category VARCHAR(64);
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS retry_after_seconds INTEGER;
                    ALTER TABLE tryon_sessions 
                        ADD COLUMN IF NOT EXISTS quota_resets_at VARCHAR(64);
                    CREATE INDEX IF NOT EXISTS ix_tryon_sessions_product_id ON tryon_sessions (product_id);
                    CREATE INDEX IF NOT EXISTS ix_tryon_sessions_user_id ON tryon_sessions (user_id);

                    CREATE TABLE IF NOT EXISTS revoked_tokens (
                        id SERIAL PRIMARY KEY,
                        token_hash VARCHAR(64) UNIQUE NOT NULL,
                        revoked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS ix_revoked_tokens_token_hash ON revoked_tokens (token_hash);
                    CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at ON revoked_tokens (expires_at);

                    ALTER TABLE products
                        ALTER COLUMN size TYPE VARCHAR(255);
                    ALTER TABLE products
                        ALTER COLUMN color TYPE VARCHAR(255);

                    ALTER TABLE shops
                        ADD COLUMN IF NOT EXISTS slug VARCHAR(120);
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_shops_slug ON shops (slug);
                """))
                conn.commit()

        # Non-destructive backfill of missing storefront slugs for existing shops
        if SessionLocal is not None:
            from app.models import Shop
            from app.core.slugs import generate_unique_shop_slug

            db = SessionLocal()
            try:
                shops_missing_slug = (
                    db.query(Shop)
                    .filter((Shop.slug.is_(None)) | (Shop.slug == ""))
                    .order_by(Shop.id.asc())
                    .all()
                )
                if shops_missing_slug:
                    for existing_shop in shops_missing_slug:
                        existing_shop.slug = generate_unique_shop_slug(
                            db,
                            existing_shop.shop_name,
                            exclude_shop_id=existing_shop.id,
                        )
                        db.flush()
                    db.commit()
                    logger.info(f"Backfilled storefront slugs for {len(shops_missing_slug)} existing shop(s).")
            except Exception as slug_exc:
                db.rollback()
                logger.warning(f"Non-fatal error while backfilling shop slugs: {slug_exc}")
            finally:
                db.close()

        logger.info("Database tables and schema alignment verified successfully.")
        return True
    except Exception as exc:
        logger.error(f"Error while verifying/creating database tables: {exc}")
        return False


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
