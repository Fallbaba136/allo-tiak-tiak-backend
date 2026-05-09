from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.rider_location import RiderLocation
from app.schemas.location import LocationUpdate, LocationOut
from app.api.dependencies import get_current_user

router = APIRouter()

# Livreur met à jour sa position
@router.post("/update", response_model=LocationOut)
def update_location(
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Seuls les livreurs peuvent mettre à jour leur position")

    location = db.query(RiderLocation).filter(RiderLocation.rider_id == current_user.id).first()
    if not location:
        location = RiderLocation(rider_id=current_user.id)
        db.add(location)

    location.latitude = payload.latitude
    location.longitude = payload.longitude
    location.order_id = payload.order_id

    db.commit()
    db.refresh(location)

    return LocationOut(
        rider_id=location.rider_id,
        latitude=location.latitude,
        longitude=location.longitude,
        order_id=location.order_id,
        updated_at=location.updated_at,
    )

# Client voit la position du livreur pour sa commande
@router.get("/order/{order_id}", response_model=LocationOut)
def get_rider_location(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.order import Order

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    if order.status not in ["accepted", "in_progress", "delivered"]:
        raise HTTPException(status_code=400, detail="Le suivi n'est pas disponible pour cette commande")

    location = db.query(RiderLocation).filter(
        RiderLocation.rider_id == order.rider_id,
        RiderLocation.order_id == order_id
    ).first()

    if not location:
        raise HTTPException(status_code=404, detail="Position du livreur non disponible")

    return LocationOut(
        rider_id=location.rider_id,
        latitude=location.latitude,
        longitude=location.longitude,
        order_id=location.order_id,
        updated_at=location.updated_at,
    )