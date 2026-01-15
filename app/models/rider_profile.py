from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class RiderProfile(Base):
    __tablename__ = "rider_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(120), nullable=True)

    payment_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)  # wave / orange_money
    payment_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # KYC plus tard

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="rider_profile")
