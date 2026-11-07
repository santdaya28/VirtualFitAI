import os
import time
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import check_db_health

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

# Initialize FastAPI application
app = FastAPI(
    title="VirtualFit AI API",
    description="High-performance asynchronous backend API for VirtualFit AI — Virtual clothing try-on and garment retailer platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Configuration
# Vite development frontend runs at http://localhost:5173
default_origins = "http://localhost:5173,http://127.0.0.1:5173"
raw_origins = os.getenv("CORS_ORIGINS", default_origins)
cors_origins: List[str] = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

# Ensure http://localhost:5173 is always present
if "http://localhost:5173" not in cors_origins:
    cors_origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
