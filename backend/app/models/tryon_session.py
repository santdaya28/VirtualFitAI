import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class TryOnSession(Base):
    __tablename__ = "tryon_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    customer_photo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    garment_id: Mapped[int] = mapped_column(Integer, ForeignKey("garments.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True
    )  # pending, processing, completed, failed
    result_image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Optional relationship to garment
    garment = relationship("Garment", lazy="joined")

