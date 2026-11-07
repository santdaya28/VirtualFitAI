import time
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_connection

router = APIRouter()
START_TIME = time.time()

@router.get("", summary="System Health & Database Connectivity Check")
def health_check():
    """
    Returns API runtime health, database connectivity status, and AI provider configuration.
    """
    db_status = check_db_connection()
    uptime_seconds = int(time.time() - START_TIME)

    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": uptime_seconds,
        "database": db_status,
        "ai_provider": {
            "configured": settings.AI_TRYON_PROVIDER,
            "status": "active" if settings.AI_TRYON_PROVIDER == "mock" or settings.FASHN_API_KEY or settings.REPLICATE_API_TOKEN else "awaiting_api_key",
        },
    }

