from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, model_validator
from app.schemas.product import ProductResponse
from app.schemas.garment import GarmentResponse


class TryOnCreateRequest(BaseModel):
    """
    Request payload to initialize a new Virtual Try-On session.
    Accepts product_id referencing the retail catalogue (products.id),
    while preserving backward compatibility for legacy garment_id.
    """
    customer_photo_url: str = Field(
        ...,
        max_length=500,
        description="URL or accessible path of the customer photo",
        examples=["https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80"],
    )
    product_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="ID of the retail catalogue product (references products.id)",
        examples=[1],
    )
    garment_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Legacy garment ID (preserved for backward compatibility)",
        examples=[1],
    )

    @model_validator(mode="after")
    def validate_product_or_garment(self) -> "TryOnCreateRequest":
        if self.product_id is None and self.garment_id is None:
            raise ValueError("Either 'product_id' or legacy 'garment_id' must be provided.")
        return self

    @property
    def target_product_id(self) -> int:
        """Helper property to retrieve the target ID regardless of whether product_id or garment_id was supplied."""
        return self.product_id if self.product_id is not None else self.garment_id  # type: ignore[return-value]


class TryOnSessionResponse(BaseModel):
    """
    Complete response model representing a Virtual Try-On session record.
    Includes product reference, AI provider, progress percentage, and stage message.
    """
    id: str = Field(..., description="Unique UUID identifier for the try-on session")
    customer_photo_url: str = Field(..., description="Customer photo URL submitted for try-on")
    product_id: Optional[int] = Field(default=None, description="Referenced catalogue product ID (products.id)")
    garment_id: Optional[int] = Field(default=None, description="Legacy garment ID (if applicable)")
    user_id: Optional[int] = Field(default=None, description="Associated customer user ID if authenticated")
    status: str = Field(default="pending", description="Session state: pending, processing, completed, failed")
    progress_percentage: int = Field(default=0, ge=0, le=100, description="Pipeline progress percentage (0-100)")
    stage_message: Optional[str] = Field(default=None, description="Current descriptive pipeline stage message")
    result_image_url: Optional[str] = Field(default=None, description="Generated try-on image URL upon completion")
    provider: str = Field(default="mock", description="AI generation provider (e.g. mock, fashn, replicate)")
    provenance: str = Field(default="mock_simulation", description="Execution provenance: 'mock_simulation', 'manual_import', or 'genuine_inference'")
    error_message: Optional[str] = Field(default=None, description="Detailed error description if status is failed")
    created_at: datetime = Field(..., description="Timestamp when the session was created (UTC)")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of the latest status update (UTC)")
    product: Optional[ProductResponse] = Field(default=None, description="Detailed product data from products catalogue")
    garment: Optional[GarmentResponse] = Field(default=None, description="Legacy garment data if associated")

    model_config = ConfigDict(from_attributes=True)


class TryOnStatusResponse(BaseModel):
    """
    Lightweight status and progress polling response for virtual try-on tasks.
    """
    session_id: str = Field(
        ...,
        validation_alias=AliasChoices("session_id", "id"),
        description="Unique UUID identifier of the session",
    )
    status: str = Field(..., description="Status of try-on task (pending, processing, completed, failed)")
    progress_percentage: int = Field(default=0, ge=0, le=100, description="Generation progress percentage (0-100)")
    stage_message: Optional[str] = Field(default=None, description="Descriptive progress message")
    message: Optional[str] = Field(default=None, description="Compatibility alias for stage_message")
    provider: str = Field(default="mock", description="Active AI provider used for generation")
    provenance: str = Field(default="mock_simulation", description="Provenance: 'mock_simulation', 'manual_import', or 'genuine_inference'")
    result_image_url: Optional[str] = Field(default=None, description="Generated try-on image URL if available")
    error_message: Optional[str] = Field(default=None, description="Error message if generation failed")
    error_category: Optional[str] = Field(default=None, description="Structured error classification if failed")
    retry_after_seconds: Optional[int] = Field(default=None, description="Recommended client wait before retrying, in seconds")
    quota_resets_at: Optional[str] = Field(default=None, description="ISO-8601 quota reset timestamp when reported by provider")
    product_id: Optional[int] = Field(default=None, description="Referenced catalogue product ID")
    shop_id: Optional[int] = Field(default=None, description="Storefront shop ID for the referenced product")
    shop_slug: Optional[str] = Field(default=None, description="Storefront slug for the referenced product")
    shop_name: Optional[str] = Field(default=None, description="Storefront name for the referenced product")
    garment_id: Optional[int] = Field(default=None, description="Legacy garment ID")
    user_id: Optional[int] = Field(default=None, description="Associated user ID if authenticated")
    is_simulation: bool = Field(default=True, description="Indicates whether this task is a mock simulation")
    created_at: Optional[datetime] = Field(default=None, description="Session creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Latest status update timestamp")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def sync_message_fields(self) -> "TryOnStatusResponse":
        if self.stage_message and not self.message:
            self.message = self.stage_message
        elif self.message and not self.stage_message:
            self.stage_message = self.message
        return self


class TryOnInputsResponse(BaseModel):
    """
    Metadata response containing exported session inputs for manual Colab inference.
    Provides customer photo download endpoint, garment image URL, and normalized category.
    """
    session_id: str = Field(..., description="Unique UUID identifier of the session")
    product_id: int = Field(..., description="Referenced catalogue product ID")
    product_name: str = Field(..., description="Name of the retail garment product")
    category: str = Field(..., description="Normalized FASHN VTON garment category (tops, bottoms, one-pieces)")
    customer_photo_download_url: str = Field(..., description="Download URL for the uploaded customer photo")
    garment_image_url: str = Field(..., description="Image URL of the selected retail garment")
    created_at: Optional[datetime] = Field(default=None, description="Session creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class TryOnHistoryItemResponse(BaseModel):
    """
    Compact item representation for customer try-on history.
    """
    session_id: str
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    shop_id: Optional[int] = None
    shop_slug: Optional[str] = None
    shop_name: Optional[str] = None
    category: Optional[str] = None
    garment_image_url: Optional[str] = None
    status: str
    progress_percentage: int
    stage_message: Optional[str] = None
    provider: str
    provenance: str
    result_image_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


