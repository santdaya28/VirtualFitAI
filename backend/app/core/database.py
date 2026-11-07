"""
Database compatibility bridge.
Re-exports the canonical database configuration from app.database.
"""
from app.database import Base, engine, SessionLocal, get_db, check_db_health

# Alias for backward compatibility
check_db_connection = check_db_health

