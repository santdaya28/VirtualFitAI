"""
Authentication & User Schemas for VirtualFit AI.
"""
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegisterRequest(BaseModel):
    """
    Registration request for new customer or shop owner.
    """
    email: str = Field(..., min_length=5, max_length=255, description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (at least 6 characters)")
    full_name: Optional[str] = Field(default=None, max_length=255, description="Full name of user")
    role: str = Field(default="customer", description="Role: 'customer' or 'shop_owner'")
    shop_name: Optional[str] = Field(default=None, max_length=255, description="Shop name if registering as shop owner")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email format.")
        return clean

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("customer", "shop_owner", "admin"):
            raise ValueError("Role must be 'customer' or 'shop_owner'.")
        return clean


class UserLoginRequest(BaseModel):
    """
    User login credential payload.
    """
    email: str = Field(..., min_length=5, max_length=255, description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email format.")
        return clean


class UserResponse(BaseModel):
    """
    Public profile representation of an authenticated User.
    """
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    shop_id: Optional[int] = None
    shop_slug: Optional[str] = None
    shop_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
    """
    Successful authentication response with bearer access token.
    """
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
