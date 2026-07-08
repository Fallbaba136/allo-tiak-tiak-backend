from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from time import time
import secrets

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate, DeliveryCodeVerify, PaymentConfirm
from app.api.dependencies import get_current_user
from app.services.notification_service import send_order_notification
from app.models.rider_profile import RiderProfile
from app.services.sms_service import send_delivery_code_sms
from app.services.payment_service import calculate_commission, get_payment_summary
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.models.price_proposal import PriceProposal

router = APIRouter()

CONFIRM_WINDOW_SECONDS = 30 * 60  # delai avant auto-confirmation apres "delivered"


def confirm_order(order: Order, db: Session, now: datetime = None) -> Order:
    """Passe la commande en 'confirmed' et calcule la commission une seule fois,
    quel que soit le chemin qui mene a la confirmation (code, client, ou auto-confirm)."""
    if order.status == "confirmed":
        return order
    if now is None:
        now = datetime.now(timezone.utc)
    order.status = "confirmed"
    order.confirmed_at = now
    if not order.commission:
        order.commission = calculate_commission(order.amount)
    db.commit()
    db.refresh(order)
    return order


def maybe_auto_confirm(order: Order, db: Session) -> Order:
    """Si la commande est toujours 'delivered' et que le delai de confirmation
    est depasse, on la confirme automatiquement (le client n'a plus besoin de cliquer)."""
    if order.status == "delivered" and order.confirm_deadline is not None:
        if int(time()) > order.confirm_deadline:
            confirm_order(order, db)
    return order


def order_to_out(o: Order, db=None) -> OrderOut:
    if db is not None:
        maybe_auto_confirm(o, db)
    client_name = None
    client_phone = None
    client_address = None
    if db is not None:
        from app.models.client_profile import ClientProfile
        from app.models.user import User as UserModel
        cp = db.query(ClientProfile).filter(ClientProfile.user_id == o.client_id).first()
        cu = db.query(UserModel).filter(UserModel.id == o.client_id).first()
        if cp:
            client_name = cp.full_name
            client_address = cp.address
        if cu:
            client_phone = cu.phone
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
        delivery_photo_url=o.delivery_photo_url,
        is_urgent=o.is_urgent,
        broadcast_expires_at=o.broadcast_expires_at,
        counter_price=o.counter_price,
        cancellation_reason=o.cancellation_reason,
        client_name=client_name,
        client_phone=client_phone,
        client_address=client_address,
    )

@router.post("/", response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Seuls les clients peuvent créer une commande")

    if payload.rider_id is not None:
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
        broadcast_expires_at=int(__import__("time").time()) + 30 * 60,
        is_urgent=payload.is_urgent,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    # Commande directe — passe en accepted automatiquement
    if payload.rider_id is not None:
        from datetime import datetime, timezone
        import random
        order.status = "accepted"
        order.accepted_at = datetime.now(timezone.utc)
        order.delivery_code = str(random.randint(100000, 999999))
        db.commit()
        db.refresh(order)
        # Notification push au livreur
        try:
            rider_profile_direct = db.query(RiderProfile).filter(RiderProfile.user_id == payload.rider_id).first()
            if rider_profile_direct and rider_profile_direct.fcm_token:
                send_order_notification(
                    fcm_token=rider_profile_direct.fcm_token,
                    order_id=order.id,
                    pickup=order.pickup_address,
                    dropoff=order.delivery_address,
                )
        except Exception as e:
            print(f"[NOTIF] Erreur notification commande directe : {e}")


    if payload.rider_id is None:
        query = db.query(RiderProfile).filter(
            RiderProfile.is_available == True,
            RiderProfile.is_verified == True,
            RiderProfile.is_blocked == False,
        )
        if payload.zone:
            query = query.filter(RiderProfile.zone.ilike(f"%{payload.zone}%"))
        available_riders = query.all()
        for rp in available_riders:
            if rp.fcm_token:
                try:
                    send_order_notification(
                        fcm_token=rp.fcm_token,
                        order_id=order.id,
                        pickup=order.pickup_address,
                        dropoff=order.delivery_address,
                    )
                except Exception as e:
                    print(f"[FCM] Erreur notification livreur {rp.user_id}: {e}")

    return order_to_out(order, db)

@router.get("/my-orders", response_model=list[OrderOut])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "client":
        orders = db.query(Order).filter(Order.client_id == current_user.id).all()
    elif current_user.role == "rider":
        from sqlalchemy import or_
        orders = db.query(Order).filter(
            or_(
                Order.rider_id == current_user.id,
                Order.cancelled_by_rider_id == current_user.id,
            )
        ).all()
    else:
        raise HTTPException(status_code=403, detail="Acces refuse")
    return [order_to_out(o, db) for o in orders]

@router.get("/pending", response_model=list[OrderOut])
def get_pending_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Reserve aux livreurs")
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile or not profile.is_verified or profile.is_blocked:
        raise HTTPException(status_code=403, detail="Profil non autorise")
    orders = db.query(Order).filter(
        Order.status == "pending",
        Order.rider_id == None,
    ).order_by(Order.created_at.desc()).all()
    return [order_to_out(o, db) for o in orders]

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
            raise HTTPException(status_code=403, detail="Action non autorisee pour le client")
        if payload.status == "cancelled":
            order.cancelled_at = now
            order.cancellation_reason = payload.cancellation_reason

    if current_user.role == "rider":
        if order.rider_id is not None and order.rider_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ce n'est pas votre livraison")
        if payload.status not in ["accepted", "in_progress", "delivered", "cancelled"]:
            raise HTTPException(status_code=403, detail="Action non autorisee pour le livreur")
        if payload.status == "cancelled":
            order.cancelled_at = now
            order.cancelled_by_rider_id = order.rider_id
            order.rider_id = None
            order.cancellation_reason = payload.cancellation_reason
    if payload.status == "accepted":
        rider_profile_check = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
        if rider_profile_check and not rider_profile_check.is_available:
                raise HTTPException(status_code=403, detail="Vous devez etre disponible pour accepter une commande")
        
        # Verrou anti double-acceptation
        from sqlalchemy import text
        result = db.execute(
                text("UPDATE orders SET status='accepted', rider_id=:rider_id, accepted_at=NOW() WHERE id=:order_id AND status='pending' AND (rider_id IS NULL OR rider_id=:rider_id)"),
                {"rider_id": current_user.id, "order_id": order_id}
        )
        db.commit()
        
        if result.rowcount == 0:
                raise HTTPException(status_code=409, detail="Cette commande a deja ete acceptee par un autre livreur")
        
        db.refresh(order)
        
        if order.order_type == "delivery":
                code = f"{secrets.randbelow(10**6):06d}"
                order.delivery_code = code
                order.delivery_code_expires_at = int(time()) + 60 * 60 * 24
                db.commit()
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
        
        order.status = payload.status
        db.commit()
        db.refresh(order)
    if payload.status == "in_progress":
        order.picked_up_at = now
    elif payload.status == "delivered":
        order.delivered_at = now
        order.confirm_deadline = int(time()) + CONFIRM_WINDOW_SECONDS
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)

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
        raise HTTPException(status_code=400, detail="La commande n'est pas encore livree")

    if not order.delivery_code:
        raise HTTPException(status_code=400, detail="Aucun code de livraison genere")

    if order.delivery_code_expires_at < int(time()):
        raise HTTPException(status_code=400, detail="Code expire")

    if payload.code != order.delivery_code:
        raise HTTPException(status_code=400, detail="Code incorrect")

    now = datetime.now(timezone.utc)
    order.delivery_code = None
    confirm_order(order, db, now)
    return order_to_out(order, db)

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
        raise HTTPException(status_code=400, detail="La commande n'est pas encore confirmee")

    rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
    if not rider_profile:
        raise HTTPException(status_code=404, detail="Profil livreur introuvable")

    return get_payment_summary(
        amount=order.amount,
        payment_method=rider_profile.payment_provider or "wave",
        rider_payment_phone=rider_profile.payment_phone,
    )

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
        raise HTTPException(status_code=400, detail="La livraison n'est pas encore confirmee")

    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Paiement deja confirme")

    now = datetime.now(timezone.utc)
    order.payment_method = payload.payment_method
    order.payment_status = "paid"
    if not order.commission:
        order.commission = calculate_commission(order.amount)
    order.payment_confirmed_at = now

    db.commit()
    db.refresh(order)
    return order_to_out(order, db)

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
        raise HTTPException(status_code=400, detail="Le trajet n'est pas encore termine")

    now = datetime.now(timezone.utc)
    confirm_order(order, db, now)
    return order_to_out(order, db)


@router.post("/{order_id}/delivery-photo", response_model=OrderOut)
async def upload_delivery_photo(
    order_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi import File
    from app.services.cloudinary_service import upload_kyc_document

    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Seuls les livreurs peuvent uploader une photo de livraison")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre livraison")

    contents = await photo.read()
    url = upload_kyc_document(contents, "delivery_photos", f"order_{order_id}_delivery")
    order.delivery_photo_url = url
    order.status = "delivered"
    order.delivered_at = datetime.now(timezone.utc)
    order.confirm_deadline = int(time()) + CONFIRM_WINDOW_SECONDS
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)
@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Reserve aux clients")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Impossible de supprimer une commande en cours")

    proposals = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id
    ).all()
    for p in proposals:
        rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == p.rider_id).first()
        if rider_profile and rider_profile.fcm_token:
            try:
                send_order_notification(
                    fcm_token=rider_profile.fcm_token,
                    order_id=order_id,
                    pickup="Commande annulee par le client",
                    dropoff="La commande #" + str(order_id) + " a ete supprimee",
                )
            except Exception as e:
                print(f"[FCM] Erreur notification: {e}")


    db.query(PriceProposal).filter(PriceProposal.order_id == order_id).delete()
    db.delete(order)
    db.commit()
    return {"message": "Commande supprimee", "order_id": order_id}



@router.post("/{order_id}/renew")
def renew_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from time import time
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Commande non disponible")
    order.broadcast_expires_at = int(time()) + 30 * 60
    db.commit()
    return {"message": "Commande renouvelee", "order_id": order_id}

@router.get("/{order_id}/rider-location")
def get_rider_location(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Reserve aux clients")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    if order.status not in ["accepted", "in_progress"]:
        raise HTTPException(status_code=400, detail="Le suivi n'est disponible que pendant une livraison active")

    if not order.rider_id:
        raise HTTPException(status_code=400, detail="Aucun livreur assigne")

    rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
    if not rider_profile or rider_profile.current_lat is None or rider_profile.current_lng is None:
        raise HTTPException(status_code=404, detail="Position du livreur indisponible")

    is_stale = False
    if rider_profile.location_updated_at:
        age_seconds = (datetime.now(timezone.utc) - rider_profile.location_updated_at).total_seconds()
        is_stale = age_seconds > 60

    return {
        "lat": rider_profile.current_lat,
        "lng": rider_profile.current_lng,
        "updated_at": rider_profile.location_updated_at,
        "is_stale": is_stale,
    }

@router.post("/{order_id}/accept-direct")
def accept_direct_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Reserve aux livreurs")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    if order.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cette commande ne vous est pas destinee")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Commande non disponible")
    from datetime import datetime, timezone
    import random
    order.status = "accepted"
    order.accepted_at = datetime.now(timezone.utc)
    order.delivery_code = str(random.randint(100000, 999999))
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)

@router.post("/{order_id}/refuse-direct")
def refuse_direct_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Reserve aux livreurs")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    if order.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cette commande ne vous est pas destinee")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Commande non disponible")
    # Remet la commande en mode automatique sans informer le client
    order.rider_id = None
    db.commit()
    db.refresh(order)
    return {"message": "Commande refusee"}
