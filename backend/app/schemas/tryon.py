from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.garment import GarmentResponse

class TryOnCreateRequest(BaseModel):
    customer_photo_url: str = Field(..., max_length=500, description="Customer photo URL or pre-signed upload URL")
    garment_id: int = Field(..., description="ID of garment to try on")

class TryOnSessionResponse(BaseModel):
    id: str
    customer_photo_url: str
    garment_id: Optional[int] = None
    status: str
    result_image_url: Optional[str] = None
    provider: str
    error_message: Optional[str] = None
    created_at: datetime
    garment: Optional[GarmentResponse] = None

    model_config = ConfigDict(from_attributes=True)

class TryOnStatusResponse(BaseModel):
    session_id: str
    status: str  # pending, processing, completed, failed
    progress_percentage: int
    message: str
    result_image_url: Optional[str] = None

