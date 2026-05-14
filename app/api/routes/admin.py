from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.order import Order
from app.models.rider_profile import RiderProfile
from app.models.dispute import Dispute
from app.models.review import Review
from app.schemas.order import OrderOut
from app.schemas.dispute import DisputeOut, DisputeResolve
from app.schemas.rider import RiderOut
from datetime import datetime, timezone

router = APIRouter()

def verify_admin(x_admin_secret: str | None = Header(default=None)):
    if x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès admin refusé")

def order_to_out(o: Order) -> dict:
    return {
        "id": o.id,
        "client_id": o.client_id,
        "rider_id": o.rider_id,
        "pickup_address": o.pickup_address,
        "delivery_address": o.delivery_address,
        "description": o.description,
        "zone": o.zone,
        "receiver_phone": o.receiver_phone,
        "status": o.status,
        "amount": o.amount,
        "commission": o.commission,
        "payment_method": o.payment_method,
        "payment_status": o.payment_status,
        "accepted_at": o.accepted_at,
        "picked_up_at": o.picked_up_at,
        "delivered_at": o.delivered_at,
        "confirmed_at": o.confirmed_at,
        "cancelled_at": o.cancelled_at,
        "payment_confirmed_at": o.payment_confirmed_at,
        "created_at": o.created_at,
    }

@router.get("/orders")
def admin_get_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [order_to_out(o) for o in orders]

@router.get("/riders")
def admin_get_riders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    riders = db.query(RiderProfile).all()
    result = []
    for r in riders:
        user = db.query(User).filter(User.id == r.user_id).first()
        result.append({
            "user_id": r.user_id,
            "phone": user.phone if user else "—",
            "full_name": r.full_name,
            "zone": r.zone,
            "payment_provider": r.payment_provider,
            "payment_phone": r.payment_phone,
            "is_available": r.is_available,
            "is_verified": r.is_verified,
            "is_blocked": r.is_blocked,
            "kyc_status": r.kyc_status,
            "kyc_rejection_reason": r.kyc_rejection_reason,
            "cni_front_url": r.cni_front_url,
            "cni_back_url": r.cni_back_url,
            "selfie_url": r.selfie_url,
            "permis_url": r.permis_url,
        })
    return result

@router.get("/disputes")
def admin_get_disputes(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    disputes = db.query(Dispute).order_by(Dispute.created_at.desc()).all()
    return disputes

@router.patch("/disputes/{dispute_id}/resolve")
def admin_resolve_dispute(
    dispute_id: int,
    payload: DisputeResolve,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")
    dispute.status = payload.status
    dispute.resolution_note = payload.resolution_note
    db.commit()
    db.refresh(dispute)
    return dispute

@router.get("/stats")
def admin_get_stats(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    total_orders = db.query(func.count(Order.id)).scalar()
    total_riders = db.query(func.count(RiderProfile.id)).scalar()
    available_riders = db.query(func.count(RiderProfile.id)).filter(RiderProfile.is_available == True).scalar()
    verified_riders = db.query(func.count(RiderProfile.id)).filter(RiderProfile.is_verified == True).scalar()
    open_disputes = db.query(func.count(Dispute.id)).filter(Dispute.status == "open").scalar()
    in_progress = db.query(func.count(Order.id)).filter(Order.status == "in_progress").scalar()
    total_commission = db.query(func.sum(Order.commission)).filter(Order.payment_status == "paid").scalar()
    total_revenue = db.query(func.sum(Order.amount)).filter(Order.payment_status == "paid").scalar()

    return {
        "total_orders": total_orders,
        "total_riders": total_riders,
        "available_riders": available_riders,
        "verified_riders": verified_riders,
        "open_disputes": open_disputes,
        "in_progress_orders": in_progress,
        "total_commission": round(total_commission or 0, 2),
        "total_revenue": round(total_revenue or 0, 2),
    }

@router.patch("/riders/{user_id}/kyc/approve")
def admin_approve_kyc(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile.kyc_status = "approved"
    profile.is_verified = True
    profile.kyc_rejection_reason = None
    db.commit()
    return {"message": "KYC approuvé", "user_id": user_id}


@router.patch("/riders/{user_id}/kyc/reject")
def admin_reject_kyc(
    user_id: int,
    reason: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile.kyc_status = "rejected"
    profile.is_verified = False
    profile.kyc_rejection_reason = reason
    db.commit()
    return {"message": "KYC rejeté", "user_id": user_id}


@router.patch("/riders/{user_id}/block")
def admin_block_rider(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile.is_blocked = not profile.is_blocked
    db.commit()
    status = "bloqué" if profile.is_blocked else "débloqué"
    return {"message": f"Livreur {status}", "user_id": user_id, "is_blocked": profile.is_blocked}


@router.delete("/riders/{user_id}")
def admin_delete_rider(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    user = db.query(User).filter(User.id == user_id).first()
    db.delete(profile)
    if user:
        db.delete(user)
    db.commit()
    return {"message": "Profil supprimé", "user_id": user_id}