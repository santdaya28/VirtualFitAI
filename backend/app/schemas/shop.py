from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ShopBase(BaseModel):
    """
    Base attributes for a retail Shop.
    """
    shop_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Official name of the garment boutique or retail store",
        examples=["Royal Heritage Garments & Boutiques"],
    )
    owner_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Name of the primary shop owner or manager",
        examples=["Vikramaditya Rao"],
    )
    email: Optional[str] = Field(
        None,
        max_length=255,
        description="Store contact email address",
        examples=["contact@royalheritage.in"],
    )
    phone: Optional[str] = Field(
        None,
        max_length=50,
        description="Primary store phone number",
        examples=["+91 98765 43210"],
    )
    address: Optional[str] = Field(
        None,
        description="Physical location / street address of the retail outlet",
        examples=["42 Commercial Street, Fashion District, Bengaluru, Karnataka 560001"],
    )


class ShopCreate(ShopBase):
    """
    Schema for creating a new shop. shop_name is strictly required.
    """
    pass


class ShopUpdate(BaseModel):
    """
    Schema for updating an existing shop. All fields are optional.
    """
    shop_name: Optional[str] = Field(None, min_length=1, max_length=255)
    owner_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    slug: Optional[str] = Field(None, min_length=1, max_length=120)


class ShopResponse(ShopBase):
    """
    Response schema returning complete shop details including database ID and creation timestamp.
    """
    id: int = Field(..., description="Unique database identifier for the shop")
    slug: Optional[str] = Field(None, description="Unique URL-safe storefront slug for the shop")
    product_count: int = Field(0, description="Number of published products available in this storefront")
    created_at: datetime = Field(..., description="Timestamp when the shop record was created (UTC)")

    model_config = ConfigDict(from_attributes=True)


class ShopListResponse(BaseModel):
    """
    Paginated summary schema for a list of shops.
    """
    total: int = Field(..., description="Total number of shops matching criteria")
    items: List[ShopResponse] = Field(..., description="List of shop records")

