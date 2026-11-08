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
        String(50),
        nullable=True,
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(50),
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


class TryOnSession(Base):
    __tablename__ = "tryon_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    customer_photo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    garment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("garments.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    result_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    garment = relationship("Garment", lazy="joined")


# Compatibility aliases for legacy import patterns
sys.modules["app.models.garment"] = sys.modules[__name__]
sys.modules["app.models.tryon_session"] = sys.modules[__name__]

__all__ = [
    "Shop",
    "Product",
    "Garment",
    "TryOnSession",
]

