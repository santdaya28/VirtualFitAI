from datetime import datetime, timezone
from sqlalchemy import String, Text, Numeric, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Garment(Base):
    __tablename__ = "garments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # Formal, Casual, Ethnic, Outerwear
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fit_type: Mapped[str] = mapped_column(String(50), nullable=True)  # Slim Fit, Regular Fit, Tailored Fit
    color: Mapped[str] = mapped_column(String(50), nullable=True)
    badge: Mapped[str] = mapped_column(String(50), nullable=True, default="Catalogue")  # Popular, Trending, etc.
    description: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

