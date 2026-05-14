from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from time import time
import secrets

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate, DeliveryCodeVerify
from app.api.dependencies import get_current_user
from app.services.notification_service import send_order_notification
from app.models.rider_profile import RiderProfile
from app.services.sms_service import send_delivery_code_sms
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate, DeliveryCodeVerify, PaymentConfirm
from app.services.payment_service import calculate_commission, get_payment_summary
from app.models.rider_profile import RiderProfile

router = APIRouter()

def order_to_out(o: Order) -> OrderOut:
    return OrderOut(
        id=o.id,
        client_id=o.client_id,
        rider_id=o.rider_id,
        pickup_address=o.pickup_address,
        delivery_address=o.delivery_address,
        description=o.description,
        zone=o.zone,
        receiver_phone=o.receiver_phone,
        status=o.status,
        order_type=o.order_type,
        amount=o.amount,
        commission=o.commission,
        payment_method=o.payment_method,
        payment_status=o.payment_status,
        accepted_at=o.accepted_at,
        picked_up_at=o.picked_up_at,
        delivered_at=o.delivered_at,
        confirmed_at=o.confirmed_at,
        cancelled_at=o.cancelled_at,
        payment_confirmed_at=o.payment_confirmed_at,
        created_at=o.created_at,
    )

@router.post("/", response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Seuls les clients peuvent créer une commande")

    rider = db.query(User).filter(User.id == payload.rider_id, User.role == "rider").first()
    if not rider:
        raise HTTPException(status_code=404, detail="Livreur introuvable")

    order = Order(
        client_id=current_user.id,
        rider_id=payload.rider_id,
        pickup_address=payload.pickup_address,
        delivery_address=payload.delivery_address,
        description=payload.description,
        zone=payload.zone,
        receiver_phone=payload.receiver_phone,
        amount=payload.amount,
        order_type=payload.order_type,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order_to_out(order)

@router.get("/my-orders", response_model=list[OrderOut])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "client":
        orders = db.query(Order).filter(Order.client_id == current_user.id).all()
    elif current_user.role == "rider":
        orders = db.query(Order).filter(Order.rider_id == current_user.id).all()
    else:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return [order_to_out(o) for o in orders]

@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    now = datetime.now(timezone.utc)

    if current_user.role == "client":
        if order.client_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")
        if payload.status not in ["cancelled", "disputed"]:
            raise HTTPException(status_code=403, detail="Action non autorisée pour le client")
        if payload.status == "cancelled":
            order.cancelled_at = now

    if current_user.role == "rider":
        if order.rider_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ce n'est pas votre livraison")
        if payload.status not in ["accepted", "in_progress", "delivered"]:
            raise HTTPException(status_code=403, detail="Action non autorisée pour le livreur")
        if payload.status == "accepted":
            order.accepted_at = now
            if order.order_type == "delivery":
                code = f"{secrets.randbelow(10**6):06d}"
                order.delivery_code = code
                order.delivery_code_expires_at = int(time()) + 60 * 60 * 24
                send_delivery_code_sms(
                    receiver_phone=order.receiver_phone,
                    code=code,
                    order_id=order.id,
                )
            rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
            if rider_profile and rider_profile.fcm_token:
                try:
                    send_order_notification(
                        fcm_token=rider_profile.fcm_token,
                        order_id=order.id,
                        pickup=order.pickup_address,
                        dropoff=order.delivery_address,
                    )
                except Exception as e:
                    print(f"[FCM] Erreur notification: {e}")
        if payload.status == "in_progress":
            order.picked_up_at = now
        if payload.status == "delivered":
            order.delivered_at = now
            # Pour transport : pas de code SMS, confirmation directe par le client

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order_to_out(order)

@router.post("/{order_id}/verify-delivery", response_model=OrderOut)
def verify_delivery_code(
    order_id: int,
    payload: DeliveryCodeVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Seuls les livreurs peuvent valider le code")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre livraison")

    if order.status != "delivered":
        raise HTTPException(status_code=400, detail="La commande n'est pas encore livrée")

    if not order.delivery_code:
        raise HTTPException(status_code=400, detail="Aucun code de livraison généré")

    if order.delivery_code_expires_at < int(time()):
        raise HTTPException(status_code=400, detail="Code expiré")

    if payload.code != order.delivery_code:
        raise HTTPException(status_code=400, detail="Code incorrect")

    now = datetime.now(timezone.utc)
    order.status = "confirmed"
    order.confirmed_at = now
    order.delivery_code = None
    db.commit()
    db.refresh(order)
    return order_to_out(order)


    # Résumé du paiement — client voit combien payer et où
@router.get("/{order_id}/payment-summary")
def get_payment_summary_route(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    if order.status != "confirmed":
        raise HTTPException(status_code=400, detail="La commande n'est pas encore confirmée")

    rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
    if not rider_profile:
        raise HTTPException(status_code=404, detail="Profil livreur introuvable")

    return get_payment_summary(
        amount=order.amount,
        payment_method=rider_profile.payment_provider or "wave",
        rider_payment_phone=rider_profile.payment_phone,
    )

# Livreur confirme la réception du paiement
@router.post("/{order_id}/confirm-payment", response_model=OrderOut)
def confirm_payment(
    order_id: int,
    payload: PaymentConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Seuls les livreurs peuvent confirmer le paiement")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre livraison")

    if order.status != "confirmed":
        raise HTTPException(status_code=400, detail="La livraison n'est pas encore confirmée")

    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Paiement déjà confirmé")

    now = datetime.now(timezone.utc)
    order.payment_method = payload.payment_method
    order.payment_status = "paid"
    order.commission = calculate_commission(order.amount)
    order.payment_confirmed_at = now

    db.commit()
    db.refresh(order)
    return order_to_out(order)


@router.post("/{order_id}/confirm-transport", response_model=OrderOut)
def confirm_transport(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Seuls les clients peuvent confirmer un trajet")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    if order.order_type != "transport":
        raise HTTPException(status_code=400, detail="Utilisez verify-delivery pour les livraisons")

    if order.status != "delivered":
        raise HTTPException(status_code=400, detail="Le trajet n'est pas encore terminé")

    now = datetime.now(timezone.utc)
    order.status = "confirmed"
    order.confirmed_at = now
    db.commit()
    db.refresh(order)
    return order_to_out(order)