from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
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
async def create_dispute(
    order_id: int = Form(...),
    accused_id: int = Form(...),
    reason: str = Form(...),
    description: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    # Garde-fou 1 — commande disputable
    if not order or order.status not in DISPUTABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Cette commande ne peut pas faire l'objet d'un litige")

    # Garde-fou 2 — impliqué dans la commande
    if order and current_user.id != order.client_id and current_user.id != order.rider_id:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas impliqué dans cette commande")

    # Garde-fou 3 — délai de 48h
    now = datetime.now(timezone.utc)
    if order.delivered_at and (now - order.delivered_at).total_seconds() > DISPUTE_DELAY_HOURS * 3600:
        raise HTTPException(status_code=400, detail="Le délai de 48h pour ouvrir un litige est dépassé")

    # Garde-fou 4 — un seul litige actif par commande
    existing = db.query(Dispute).filter(
        Dispute.order_id == order_id,
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
        order_id=order_id,
        reason=reason,
        description=description,
        order_snapshot=order_snapshot,
        photo_url=None,
        status="open",
        expires_at=now + timedelta(days=DISPUTE_RETENTION_DAYS),
    )
    if photo and photo.filename:
        try:
            from app.services.cloudinary_service import upload_kyc_document
            contents = await photo.read()
            url = upload_kyc_document(contents, "dispute_photos", f"dispute_{order_id}_{current_user.id}")
            dispute.photo_url = url
            print(f"[PHOTO] Photo litige uploadee : {url}")
        except Exception as e:
            print(f"[PHOTO] Erreur upload : {e}")

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
            reason=reason,
            description=description,
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
@router.post("/contact-support")
async def contact_support(
    subject: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        from app.services.email_service import send_support_message
        send_support_message(
            user_phone=current_user.phone,
            subject=subject,
            message=message,
        )
    except Exception as e:
        print(f"[EMAIL] Erreur : {e}")

    # Notifier le client si c'est un problème de paiement
    try:
        import re
        match = re.search(r'Commande #(\d+)', message)
        if match and current_user.role == "rider":
            order_id = int(match.group(1))
            from app.models.order import Order
            from app.models.client_profile import ClientProfile
            from app.services.notification_service import send_notification
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
                if client_profile and client_profile.fcm_token:
                    send_notification(
                        fcm_token=client_profile.fcm_token,
                        title="⚠️ Problème de paiement signalé",
                        body=f"Le livreur a signalé un problème sur votre commande #{order_id}. Notre équipe va vous contacter.",
                        data={"order_id": str(order_id), "type": "payment_issue"}
                    )
    except Exception as e:
        print(f"[NOTIF] Erreur notif client litige : {e}")

    return {"message": "Message envoye avec succes"}

@router.post("/{dispute_id}/respond")
def respond_to_dispute(
    dispute_id: int,
    response: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    if current_user.id == dispute.complainant_id or current_user.id == dispute.accused_id:
        # Déterminer si c'est le client ou le livreur
        from app.models.order import Order
        order = db.query(Order).filter(Order.id == dispute.order_id).first()
        if order and current_user.id == order.client_id:
            dispute.client_response = response
            dispute.client_response_at = now
            # Notifier le rider
            try:
                from app.models.rider_profile import RiderProfile
                from app.services.notification_service import send_notification
                rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
                if rider_profile and rider_profile.fcm_token:
                    send_notification(
                        fcm_token=rider_profile.fcm_token,
                        title="💬 Le client a répondu au litige",
                        body=response[:80],
                        data={"dispute_id": str(dispute_id), "type": "dispute_response"}
                    )
            except Exception as e:
                print(f"[NOTIF] Erreur : {e}")
        elif order and current_user.id == order.rider_id:
            dispute.rider_response = response
            dispute.rider_response_at = now
            # Notifier le client
            try:
                from app.models.client_profile import ClientProfile
                from app.services.notification_service import send_notification
                client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
                if client_profile and client_profile.fcm_token:
                    send_notification(
                        fcm_token=client_profile.fcm_token,
                        title="💬 Le livreur a répondu au litige",
                        body=response[:80],
                        data={"dispute_id": str(dispute_id), "type": "dispute_response"}
                    )
            except Exception as e:
                print(f"[NOTIF] Erreur : {e}")
    else:
        raise HTTPException(status_code=403, detail="Non autorisé")
    
    dispute.status = "under_review"
    db.commit()
    return {"message": "Réponse envoyée"}

@router.patch("/{dispute_id}/admin-resolve")
def admin_resolve_dispute(
    dispute_id: int,
    resolution_note: str,
    resolution_favor: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Reserve aux admins")
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")
    
    dispute.status = "resolved"
    dispute.resolution_note = resolution_note
    dispute.resolution_favor = resolution_favor
    dispute.resolved_by_id = current_user.id
    db.commit()

    # Notifier les deux parties
    try:
        from app.models.order import Order
        from app.models.client_profile import ClientProfile
        from app.models.rider_profile import RiderProfile
        from app.services.notification_service import send_notification
        order = db.query(Order).filter(Order.id == dispute.order_id).first()
        if order:
            favor_label = "votre faveur" if resolution_favor == "client" else "celle du livreur"
            client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
            if client_profile and client_profile.fcm_token:
                send_notification(
                    fcm_token=client_profile.fcm_token,
                    title="✅ Litige résolu",
                    body=f"Le litige a été résolu en {favor_label}. {resolution_note}",
                    data={"dispute_id": str(dispute_id), "type": "dispute_resolved"}
                )
            rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
            if rider_profile and rider_profile.fcm_token:
                favor_label_r = "votre faveur" if resolution_favor == "rider" else "celle du client"
                send_notification(
                    fcm_token=rider_profile.fcm_token,
                    title="✅ Litige résolu",
                    body=f"Le litige a été résolu en {favor_label_r}. {resolution_note}",
                    data={"dispute_id": str(dispute_id), "type": "dispute_resolved"}
                )
    except Exception as e:
        print(f"[NOTIF] Erreur : {e}")

    return {"message": "Litige résolu"}
