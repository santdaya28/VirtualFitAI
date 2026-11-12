import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    Numeric,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Shop(Base):
    """
    Shop entity representing a garment retailer in the VirtualFit AI platform.
    """
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    shop_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    slug: Mapped[Optional[str]] = mapped_column(
        String(120),
        unique=True,
        nullable=True,
        index=True,
    )
    owner_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # One-to-many relationship: One Shop can have multiple Products
    products: Mapped[List["Product"]] = relationship(
        "Product",
        back_populates="shop",
        cascade="all, delete-orphan",
    )

    # One-to-many relationship: One Shop can have multiple associated users (staff/owners)
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="shop",
    )

    def __repr__(self) -> str:
        return f"<Shop(id={self.id}, shop_name='{self.shop_name}')>"


class Product(Base):
    """
    Product entity representing a garment item belonging to a retail Shop.
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    shop_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    size: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to parent Shop
    shop: Mapped["Shop"] = relationship(
        "Shop",
        back_populates="products",
    )

    # One-to-many relationship: One Product can have multiple TryOnSessions
    tryon_sessions: Mapped[List["TryOnSession"]] = relationship(
        "TryOnSession",
        back_populates="product",
    )

    def __repr__(self) -> str:
        return (
            f"<Product(id={self.id}, shop_id={self.shop_id}, "
            f"product_name='{self.product_name}', price={self.price})>"
        )


# Backward-compatible model definitions for legacy try-on references
class Garment(Base):
    __tablename__ = "garments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fit_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    badge: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="Catalogue")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class User(Base):
    """
    User entity representing customers and shop owners in the VirtualFit AI platform.
    Supports role-based access control (role="customer" | "shop_owner" | "admin").
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default="customer",
        nullable=False,
        index=True,
    )
    shop_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    shop: Mapped[Optional["Shop"]] = relationship("Shop", back_populates="users", lazy="joined")

    @property
    def shop_slug(self) -> Optional[str]:
        return self.shop.slug if self.shop is not None else None

    @property
    def shop_name(self) -> Optional[str]:
        return self.shop.shop_name if self.shop is not None else None
    tryon_sessions: Mapped[List["TryOnSession"]] = relationship("TryOnSession", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class TryOnSession(Base):
    """
    TryOnSession entity tracking an AI virtual clothing try-on task.
    References the real catalogue product (Product) while preserving
    legacy compatibility with Garment if needed.
    """
    __tablename__ = "tryon_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    customer_photo_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Primary reference: ForeignKey pointing to products.id
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional reference to customer User account for history and session isolation
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Legacy reference: preserved for backward compatibility
    garment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("garments.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    # Provenance tracking: "mock_simulation" | "manual_import" | "genuine_inference"
    provenance: Mapped[str] = mapped_column(String(50), default="mock_simulation", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retry_after_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quota_resets_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="tryon_sessions", lazy="joined")
    garment: Mapped[Optional["Garment"]] = relationship("Garment", lazy="joined")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="tryon_sessions", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<TryOnSession(id='{self.id}', product_id={self.product_id}, "
            f"user_id={self.user_id}, status='{self.status}', "
            f"progress={self.progress_percentage}%, provider='{self.provider}', "
            f"provenance='{self.provenance}')>"
        )


class RevokedToken(Base):
    """
    Stores revoked bearer token hashes for server-side logout validation.
    Tokens are tracked until their natural expiration timestamp, after which
    they are safely purged.
    """
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<RevokedToken(id={self.id}, hash='{self.token_hash[:8]}...', expires_at='{self.expires_at}')>"


# Compatibility aliases for legacy import patterns
sys.modules["app.models.garment"] = sys.modules[__name__]
sys.modules["app.models.tryon_session"] = sys.modules[__name__]

__all__ = [
    "User",
    "Shop",
    "Product",
    "Garment",
    "TryOnSession",
    "RevokedToken",
]

