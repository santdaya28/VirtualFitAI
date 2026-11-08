from app.schemas.shop import (
    ShopBase,
    ShopCreate,
    ShopUpdate,
    ShopResponse,
    ShopListResponse,
)
from app.schemas.product import (
    ProductBase,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)
from app.schemas.garment import (
    GarmentBase,
    GarmentCreate,
    GarmentUpdate,
    GarmentResponse,
    GarmentListResponse,
)
from app.schemas.tryon import (
    TryOnCreateRequest,
    TryOnSessionResponse,
    TryOnStatusResponse,
)

__all__ = [
    # Shop Schemas
    "ShopBase",
    "ShopCreate",
    "ShopUpdate",
    "ShopResponse",
    "ShopListResponse",
    # Product Schemas
    "ProductBase",
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductListResponse",
    # Legacy Garment & TryOn Schemas
    "GarmentBase",
    "GarmentCreate",
    "GarmentUpdate",
    "GarmentResponse",
    "GarmentListResponse",
    "TryOnCreateRequest",
    "TryOnSessionResponse",
    "TryOnStatusResponse",
]
