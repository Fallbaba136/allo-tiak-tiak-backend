from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.api.dependencies import get_current_user

router = APIRouter()

# Bilan mensuel client
@router.get("/client/monthly")
def client_monthly_stats(
    month: int,
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Accès réservé aux clients")

    orders = db.query(Order).filter(
        Order.client_id == current_user.id,
        Order.status == "confirmed",
        extract("month", Order.created_at) == month,
        extract("year", Order.created_at) == year,
    ).all()

    total_spent = sum(o.amount or 0 for o in orders)

    return {
        "month": month,
        "year": year,
        "total_orders": len(orders),
        "total_spent": total_spent,
        "orders": [
            {
                "id": o.id,
                "date": str(o.created_at),
                "amount": o.amount,
                "delivery_address": o.delivery_address,
                "rider_id": o.rider_id,
                "status": o.status,
            }
            for o in orders
        ]
    }

# Bilan mensuel livreur
@router.get("/rider/monthly")
def rider_monthly_stats(
    month: int,
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Accès réservé aux livreurs")

    from app.models.review import Review
    from sqlalchemy import func

    orders = db.query(Order).filter(
        Order.rider_id == current_user.id,
        Order.status == "confirmed",
        extract("month", Order.created_at) == month,
        extract("year", Order.created_at) == year,
    ).all()

    total_revenue = sum((o.amount or 0) - (o.commission or 0) for o in orders)

    avg_rating = db.query(func.avg(Review.rating)).filter(
        Review.rider_id == current_user.id,
        extract("month", Review.created_at) == month,
        extract("year", Review.created_at) == year,
    ).scalar()

    return {
        "month": month,
        "year": year,
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "average_rating": round(float(avg_rating or 0), 2),
        "orders": [
            {
                "id": o.id,
                "date": str(o.created_at),
                "amount": o.amount,
                "commission": o.commission,
                "revenue": (o.amount or 0) - (o.commission or 0),
                "pickup_address": o.pickup_address,
                "delivery_address": o.delivery_address,
                "status": o.status,
            }
            for o in orders
        ]
    }