from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class GarmentBase(BaseModel):
    name: str = Field(..., max_length=255, description="Garment display name")
    category: str = Field(..., max_length=100, description="Formal, Casual, Ethnic, Outerwear")
    price: float = Field(..., ge=0, description="Price in currency units")
    fit_type: Optional[str] = Field("Regular Fit", max_length=50)
    color: Optional[str] = Field(None, max_length=50)
    badge: Optional[str] = Field("Catalogue", max_length=50)
    description: Optional[str] = Field(None, description="Detailed product description")
    image_url: str = Field(..., max_length=500, description="Public CDN or static asset URL")

class GarmentCreate(GarmentBase):
    pass

class GarmentUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    fit_type: Optional[str] = None
    color: Optional[str] = None
    badge: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

class GarmentResponse(GarmentBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class GarmentListResponse(BaseModel):
    total: int
    items: List[GarmentResponse]
    categories: List[str]

