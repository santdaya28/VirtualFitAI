from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ProductBase(BaseModel):
    """
    Base attributes for a garment product.
    """
    product_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Garment display name",
        examples=["Midnight Navy Silk Blazer"],
    )
    description: Optional[str] = Field(
        None,
        description="Detailed product description and material info",
        examples=["Handcrafted luxury silk-blend tailored formal blazer."],
    )
    category: Optional[str] = Field(
        None,
        max_length=100,
        description="Category classification (e.g. Formal, Casual, Ethnic, Outerwear)",
        examples=["Formal"],
    )
    price: Decimal = Field(
        ...,
        ge=0,
        description="Product price in currency units (e.g. ₹ or $). Uses exact decimal representation.",
        examples=[4999.00],
    )
    size: Optional[str] = Field(
        None,
        max_length=255,
        description="Available garment sizes",
        examples=["S, M, L, XL"],
    )
    color: Optional[str] = Field(
        None,
        max_length=255,
        description="Primary color or color palette",
        examples=["Navy Blue"],
    )
    image_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL or static asset path for product preview. Never stores binary images in DB.",
        examples=["https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80"],
    )
    stock_quantity: int = Field(
        default=0,
        ge=0,
        description="Available inventory count in units",
        examples=[25],
    )
    is_available: bool = Field(
        default=True,
        description="Flag indicating if item is actively listed for customer catalogue and try-on",
        examples=[True],
    )


class ProductCreate(ProductBase):
    """
    Schema for creating a new product. For shop owners, shop_id is derived from the authenticated shop if omitted.
    """
    shop_id: Optional[int] = Field(
        None,
        ge=1,
        description="Optional Shop ID; derived server-side from the authenticated shop owner when omitted",
        examples=[1],
    )


class ProductUpdate(BaseModel):
    """
    Schema for updating an existing product. All fields are optional.
    """
    shop_id: Optional[int] = Field(None, ge=1, description="New shop ID if moving product to another shop")
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    price: Optional[Decimal] = Field(None, ge=0)
    size: Optional[str] = Field(None, max_length=255)
    color: Optional[str] = Field(None, max_length=255)
    image_url: Optional[str] = Field(None, max_length=500)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_available: Optional[bool] = None


class ProductResponse(ProductBase):
    """
    Complete product response schema including database ID, parent shop ID, and creation timestamp.
    """
    id: int = Field(..., description="Unique database identifier for the product")
    shop_id: int = Field(..., description="Foreign key ID referencing the owning Shop")
    created_at: datetime = Field(..., description="Timestamp when the product was created (UTC)")

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    """
    Paginated summary schema for listing products with total count.
    """
    total: int = Field(..., description="Total count matching search and filter criteria")
    items: List[ProductResponse] = Field(..., description="List of product records")
    skip: int = Field(..., description="Number of items skipped for pagination")
    limit: int = Field(..., description="Maximum items per page returned")

