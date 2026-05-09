from sqlalchemy import String, ForeignKey, DateTime, func, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Qui se plaint, contre qui, sur quelle commande
    complainant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    accused_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)

    # Détails du litige
    reason: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)

    # Snapshot de la commande au moment du litige
    order_snapshot: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Statut
    status: Mapped[str] = mapped_column(String(30), default="open")
    # open / under_review / resolved / rejected

    # Score de fiabilité
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)

    # Résolution
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Rétention — suppression après 1 an
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True))

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    complainant = relationship("User", foreign_keys=[complainant_id])
    accused = relationship("User", foreign_keys=[accused_id])
    order = relationship("Order", foreign_keys=[order_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])