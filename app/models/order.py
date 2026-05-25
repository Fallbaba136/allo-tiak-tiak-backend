from sqlalchemy import String, ForeignKey, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rider_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    pickup_address: Mapped[str] = mapped_column(String(255))
    delivery_address: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Receveur
    receiver_phone: Mapped[str] = mapped_column(String(30))
    delivery_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    delivery_code_expires_at: Mapped[int | None] = mapped_column(nullable=True)  # epoch seconds

    status: Mapped[str] = mapped_column(String(30), default="pending")
    # pending / accepted / in_progress / delivered / confirmed / cancelled / disputed
    order_type: Mapped[str] = mapped_column(String(20), default="delivery")
    # delivery / transport
    receiver_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    accepted_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    

    # Paiement
    amount: Mapped[float | None] = mapped_column(nullable=True)  # montant en FCFA
    commission: Mapped[float | None] = mapped_column(nullable=True)  # commission plateforme
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)  # wave / orange_money
    payment_status: Mapped[str] = mapped_column(String(30), default="pending")
    delivery_photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # pending / paid / commission_due
    payment_confirmed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client = relationship("User", foreign_keys=[client_id])
    rider = relationship("User", foreign_keys=[rider_id])