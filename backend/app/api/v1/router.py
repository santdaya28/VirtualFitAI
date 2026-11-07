from fastapi import APIRouter
from app.api.v1.endpoints import health, garments, tryon

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, prefix="/health", tags=["System Health"])
api_v1_router.include_router(garments.router, prefix="/garments", tags=["Catalogue Garments"])
api_v1_router.include_router(tryon.router, prefix="/tryon", tags=["Virtual Try-On"])

