from sqlalchemy import Float, ForeignKey, DateTime, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class RiderLocation(Base):
    __tablename__ = "rider_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    rider_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    rider = relationship("User", foreign_keys=[rider_id])