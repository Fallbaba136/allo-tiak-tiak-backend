from sqlalchemy import String, ForeignKey, DateTime, func, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rider_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    rating: Mapped[int] = mapped_column(Integer)  # 1 à 5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", foreign_keys=[order_id])
    client = relationship("User", foreign_keys=[client_id])
    rider = relationship("User", foreign_keys=[rider_id])