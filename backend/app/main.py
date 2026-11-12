import os
import time
import logging
from pathlib import Path
from typing import List
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import check_db_health, init_db
from app.models import Shop, Product, User  # Ensures models are registered with Base.metadata
from app.routers import shops_router, products_router, tryon_router, auth_router
from app.core.security import SECRET_KEY

# Load environment variables from backend/.env regardless of execution directory
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("virtualfit.main")

START_TIME = time.time()
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Safely creates database tables for registered models on startup without dropping existing data.
    Validates production security configurations.
    """
    logger.info(f"Initializing VirtualFit AI Backend (Environment: {ENVIRONMENT})...")

    # Production configuration validation
    if ENVIRONMENT == "production":
        if SECRET_KEY == "virtualfit_ai_production_grade_secret_key_2026_super_secure":
            logger.critical(
                "CRITICAL SECURITY WARNING: Default insecure SECRET_KEY detected in production environment! "
                "Set a cryptographically strong, random SECRET_KEY in your environment."
            )
        if "*" in cors_origins:
            logger.warning(
                "SECURITY WARNING: Wildcard '*' CORS origin is active in production mode. "
                "Restrict CORS_ORIGINS to specific authorized domains."
            )

    # Initialize/verify database tables if PostgreSQL is connected
    health = check_db_health()
    if health.get("status") == "connected":
        init_db()
        logger.info("Database models 'shops', 'products', 'users', 'tryon_sessions' verified.")
    else:
        logger.info(f"Database status at startup: {health.get('status')} - {health.get('message')}")
    yield
    logger.info("VirtualFit AI Backend shutting down.")


# Initialize FastAPI application
app = FastAPI(
    title="VirtualFit AI API",
    description="High-performance asynchronous backend API for VirtualFit AI — Virtual clothing try-on and garment retailer platform.",
    version="1.0.0",
    docs_url="/docs" if ENVIRONMENT != "production" else None,  # Hide docs in production if desired or configure
    redoc_url="/redoc" if ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# Standard Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Adds baseline defensive HTTP headers to all API responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Global Unhandled Exception Handler (API Error Sanitization)
@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches all unexpected exceptions and returns a clean, sanitized response.
    Guarantees internal Python stack traces, file paths, or DB errors are never leaked to clients.
    """
    if isinstance(exc, (StarletteHTTPException,)):
        # Let explicit HTTPExceptions pass through untouched
        raise exc

    logger.exception(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "detail": "An internal server error occurred. Our engineering team has been notified.",
            "code": "INTERNAL_SERVER_ERROR",
        },
    )


# CORS Configuration
# Vite development frontend runs at http://localhost:5173
default_origins = "http://localhost:5173,http://127.0.0.1:5173"
raw_origins = os.getenv("CORS_ORIGINS", default_origins)
cors_origins: List[str] = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

# Ensure http://localhost:5173 is always present in development
if ENVIRONMENT != "production" and "http://localhost:5173" not in cors_origins:
    cors_origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(shops_router)
app.include_router(products_router)
app.include_router(tryon_router)

# Mount uploads directory for static product images
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.get(
    "/",
    summary="Root Welcome Endpoint",
    tags=["General"],
    response_description="Welcome message and API service overview",
)
def read_root():
    """
    Root endpoint returning a welcome message, API version, and links to documentation and health status.
    """
    return {
        "message": "Welcome to the VirtualFit AI API",
        "service": "VirtualFit AI API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "health": "/api/health",
    }

@app.get(
    "/api/health",
    summary="API Health Status Check",
    tags=["Health"],
    response_description="Current API operational health and database connectivity",
)
@app.get("/health", include_in_schema=False)
def health_check():
    """
    Returns current API runtime status, uptime in seconds, and PostgreSQL database connectivity.
    """
    uptime_seconds = int(time.time() - START_TIME)
    db_status = check_db_health()

    return {
        "status": "healthy",
        "service": "VirtualFit AI API",
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds,
        "database": db_status,
        "cors_origins": cors_origins,
    }

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
