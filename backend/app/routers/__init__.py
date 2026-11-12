"""
FastAPI route modules for VirtualFit AI.
"""
from app.routers.shops import router as shops_router
from app.routers.products import router as products_router
from app.routers.tryon import router as tryon_router
from app.routers.auth import router as auth_router

__all__ = ["shops_router", "products_router", "tryon_router", "auth_router"]

