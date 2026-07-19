from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from app.db.session import get_db
from app.models.message import Message
from app.models.order import Order
from app.models.user import User
from app.models.price_proposal import PriceProposal
from app.api.dependencies import get_current_user

router = APIRouter()

@router.get("/orders/{order_id}/messages")
def get_messages(
    order_id: int,
    rider_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    # Vérifier que l'utilisateur est concerné par cette commande
    # Vérifier que l'utilisateur est le client, le livreur assigné, ou un livreur qui a proposé
    has_proposal = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.rider_id == current_user.id
    ).first()
    if current_user.id != order.client_id and current_user.id != order.rider_id and not has_proposal:
        raise HTTPException(status_code=403, detail="Accès refusé")
    # Supprimer les messages expirés
    now = datetime.now(timezone.utc)
    db.query(Message).filter(Message.expires_at < now).delete()
    db.commit()
    # Filtrer par rider_id si fourni
    query = db.query(Message).filter(Message.order_id == order_id)
    if rider_id:
        query = query.filter(
            (Message.rider_id == rider_id) | (Message.rider_id == None)
        )
    messages = query.order_by(Message.created_at.asc()).all()
    return [{
        "id": m.id,
        "sender_id": m.sender_id,
        "content": m.content,
        "created_at": m.created_at.isoformat(),
        "is_mine": m.sender_id == current_user.id,
    } for m in messages]

@router.post("/orders/{order_id}/messages")
def send_message(
    order_id: int,
    content: str,
    rider_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Message vide")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    # Vérifier que l'utilisateur est le client, le livreur assigné, ou un livreur qui a proposé
    has_proposal = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.rider_id == current_user.id
    ).first()
    if current_user.id != order.client_id and current_user.id != order.rider_id and not has_proposal:
        raise HTTPException(status_code=403, detail="Accès refusé")
    # Déterminer le rider_id de cette conversation
    conversation_rider_id = rider_id or (order.rider_id if order.rider_id else (current_user.id if current_user.role == 'rider' else None))
    msg = Message(
        order_id=order_id,
        sender_id=current_user.id,
        content=content.strip(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        rider_id=conversation_rider_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # Notifier l'autre partie
    try:
        from app.services.notification_service import send_notification
        from app.models.client_profile import ClientProfile
        from app.models.rider_profile import RiderProfile
        if current_user.id == order.client_id:
            # Client envoie → notifier le livreur (assigné ou celui qui a proposé)
            rider_id = order.rider_id or (has_proposal.rider_id if has_proposal else None)
            if rider_id:
                rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == rider_id).first()
                if rider_profile and rider_profile.fcm_token:
                    send_notification(
                        fcm_token=rider_profile.fcm_token,
                        title="💬 Message du client",
                        body=msg.content[:80],
                        data={"order_id": str(order_id), "type": "new_message"}
                    )
        else:
            # Livreur envoie → notifier le client
            client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
            if client_profile and client_profile.fcm_token:
                send_notification(
                    fcm_token=client_profile.fcm_token,
                    title="💬 Message du livreur",
                    body=msg.content[:80],
                    data={"order_id": str(order_id), "type": "new_message"}
                )
    except Exception as e:
        print(f"[NOTIF] Erreur message : {e}")
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
        "is_mine": True,
    }
