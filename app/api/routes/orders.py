from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate
from app.api.dependencies import get_current_user

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
        status=o.status,
        accepted_at=o.accepted_at,
        picked_up_at=o.picked_up_at,
        delivered_at=o.delivered_at,
        confirmed_at=o.confirmed_at,
        cancelled_at=o.cancelled_at,
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
        if payload.status not in ["cancelled", "confirmed", "disputed"]:
            raise HTTPException(status_code=403, detail="Action non autorisée pour le client")
        if payload.status == "cancelled":
            order.cancelled_at = now
        if payload.status == "confirmed":
            order.confirmed_at = now

    if current_user.role == "rider":
        if order.rider_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ce n'est pas votre livraison")
        if payload.status not in ["accepted", "in_progress", "delivered"]:
            raise HTTPException(status_code=403, detail="Action non autorisée pour le livreur")
        if payload.status == "accepted":
            order.accepted_at = now
        if payload.status == "in_progress":
            order.picked_up_at = now
        if payload.status == "delivered":
            order.delivered_at = now

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order_to_out(order)