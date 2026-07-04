from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.models.dispute import Dispute
from app.schemas.dispute import DisputeCreate, DisputeOut, DisputeResolve
from app.api.dependencies import get_current_user

router = APIRouter()

DISPUTABLE_STATUSES = ["delivered", "confirmed"]
DISPUTE_DELAY_HOURS = 48
DISPUTE_RETENTION_DAYS = 365

def dispute_to_out(d: Dispute) -> DisputeOut:
    return DisputeOut(
        id=d.id,
        complainant_id=d.complainant_id,
        accused_id=d.accused_id,
        order_id=d.order_id,
        reason=d.reason,
        description=d.description,
        status=d.status,
        resolution_note=d.resolution_note,
        expires_at=d.expires_at,
        created_at=d.created_at,
    )

# Client ou livreur ouvre un litige
@router.post("/", response_model=DisputeOut)
def create_dispute(
    payload: DisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    # Garde-fou 1 — commande disputable
    if order.status not in DISPUTABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Cette commande ne peut pas faire l'objet d'un litige")

    # Garde-fou 2 — impliqué dans la commande
    if current_user.id != order.client_id and current_user.id != order.rider_id:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas impliqué dans cette commande")

    # Garde-fou 3 — délai de 48h
    now = datetime.now(timezone.utc)
    if order.delivered_at and (now - order.delivered_at).total_seconds() > DISPUTE_DELAY_HOURS * 3600:
        raise HTTPException(status_code=400, detail="Le délai de 48h pour ouvrir un litige est dépassé")

    # Garde-fou 4 — un seul litige actif par commande
    existing = db.query(Dispute).filter(
        Dispute.order_id == payload.order_id,
        Dispute.status.in_(["open", "under_review"])
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un litige est déjà ouvert pour cette commande")

    # Déterminer l'accusé
    accused_id = order.rider_id if current_user.id == order.client_id else order.client_id

    # Snapshot de la commande
    order_snapshot = {
        "id": order.id,
        "status": order.status,
        "pickup_address": order.pickup_address,
        "delivery_address": order.delivery_address,
        "description": order.description,
        "amount": order.amount,
        "payment_status": order.payment_status,
        "created_at": str(order.created_at),
        "delivered_at": str(order.delivered_at),
    }

    dispute = Dispute(
        complainant_id=current_user.id,
        accused_id=accused_id,
        order_id=payload.order_id,
        reason=payload.reason,
        description=payload.description,
        order_snapshot=order_snapshot,
        status="open",
        expires_at=now + timedelta(days=DISPUTE_RETENTION_DAYS),
    )

    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    # Notification email admin
    try:
        from app.services.email_service import send_dispute_notification
        from app.models.rider_profile import RiderProfile
        rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
        client = db.query(User).filter(User.id == order.client_id).first()
        rider = db.query(User).filter(User.id == order.rider_id).first()
        send_dispute_notification(
            order_id=order.id,
            client_phone=client.phone if client else "inconnu",
            rider_phone=rider.phone if rider else "inconnu",
            rider_name=rider_profile.full_name if rider_profile else None,
            reason=payload.reason,
            description=payload.description,
        )
    except Exception as e:
        print(f"[EMAIL] Erreur notification litige : {e}")

    return dispute_to_out(dispute)

# Voir ses litiges
@router.get("/my-disputes", response_model=list[DisputeOut])
def get_my_disputes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    disputes = db.query(Dispute).filter(
        (Dispute.complainant_id == current_user.id) |
        (Dispute.accused_id == current_user.id)
    ).all()
    return [dispute_to_out(d) for d in disputes]

# Admin résout un litige
@router.patch("/{dispute_id}/resolve", response_model=DisputeOut)
def resolve_dispute(
    dispute_id: int,
    payload: DisputeResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Seul l'admin peut résoudre un litige")

    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")

    if dispute.status not in ["open", "under_review"]:
        raise HTTPException(status_code=400, detail="Ce litige est déjà résolu")

    dispute.status = payload.status
    dispute.resolution_note = payload.resolution_note
    dispute.resolved_by_id = current_user.id

    # Si rejeté → incrémenter le score de fiabilité du plaignant
    if payload.status == "rejected":
        dispute.rejected_count += 1

    db.commit()
    db.refresh(dispute)
    return dispute_to_out(dispute)