"""
FastAPI route modules for VirtualFit AI.
"""
from app.routers.shops import router as shops_router
from app.routers.products import router as products_router

__all__ = ["shops_router", "products_router"]
