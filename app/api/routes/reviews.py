from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewOut, RiderRatingSummary
from app.api.dependencies import get_current_user

router = APIRouter()

def review_to_out(r: Review) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        order_id=r.order_id,
        client_id=r.client_id,
        rider_id=r.rider_id,
        rating=r.rating,
        comment=r.comment,
        created_at=r.created_at,
    )

# Client laisse un avis sur un livreur
@router.post("/", response_model=ReviewOut)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Seuls les clients peuvent laisser un avis")

    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    if order.status != "confirmed":
        raise HTTPException(status_code=400, detail="Vous ne pouvez laisser un avis que sur une commande confirmée")

    # Un seul avis par commande
    existing = db.query(Review).filter(Review.order_id == payload.order_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vous avez déjà laissé un avis pour cette commande")

    review = Review(
        order_id=payload.order_id,
        client_id=current_user.id,
        rider_id=order.rider_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review_to_out(review)

# Voir les avis d'un livreur
@router.get("/rider/{rider_id}", response_model=list[ReviewOut])
def get_rider_reviews(
    rider_id: int,
    db: Session = Depends(get_db),
):
    reviews = db.query(Review).filter(Review.rider_id == rider_id).all()
    return [review_to_out(r) for r in reviews]

# Résumé des notes d'un livreur
@router.get("/rider/{rider_id}/summary", response_model=RiderRatingSummary)
def get_rider_summary(
    rider_id: int,
    db: Session = Depends(get_db),
):
    result = db.query(
        func.avg(Review.rating).label("average_rating"),
        func.count(Review.id).label("total_reviews"),
    ).filter(Review.rider_id == rider_id).first()

    total_orders = db.query(Order).filter(
        Order.rider_id == rider_id,
        Order.status == "confirmed"
    ).count()

    return RiderRatingSummary(
        rider_id=rider_id,
        average_rating=round(float(result.average_rating or 0), 2),
        total_reviews=result.total_reviews,
        total_orders=total_orders,
    )