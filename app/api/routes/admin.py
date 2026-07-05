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

def order_to_out(o: Order, db=None) -> dict:
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
    return {
        "id": o.id,
        "client_id": o.client_id,
        "client_name": client_name,
        "client_phone": client_phone,
        "client_address": client_address,
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
        "is_urgent": o.is_urgent,
    }

@router.get("/orders")
def admin_get_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [order_to_out(o, db) for o in orders]

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
    from app.models.client_profile import ClientProfile
    from app.models.rider_profile import RiderProfile
    disputes = db.query(Dispute).order_by(Dispute.created_at.desc()).all()
    result = []
    for d in disputes:
        complainant = db.query(User).filter(User.id == d.complainant_id).first()
        accused = db.query(User).filter(User.id == d.accused_id).first()
        client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == d.complainant_id).first()
        rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == d.accused_id).first()
        result.append({
            "id": d.id,
            "order_id": d.order_id,
            "status": d.status,
            "reason": d.reason,
            "description": d.description,
            "resolution_note": d.resolution_note,
            "expires_at": d.expires_at.isoformat() if d.expires_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "complainant_id": d.complainant_id,
            "accused_id": d.accused_id,
            "client_phone": complainant.phone if complainant else None,
            "client_name": client_profile.full_name if client_profile else None,
            "client_address": client_profile.address if client_profile else None,
            "rider_name": rider_profile.full_name if rider_profile else None,
            "rider_phone": accused.phone if accused else None,
            "photo_url": d.photo_url,
        })
    return result

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

    user = db.query(User).filter(User.id == user_id).first()

    # Notification FCM push
    if profile.fcm_token:
        try:
            from app.firebase.firebase_init import get_firebase_app
            from firebase_admin import messaging
            get_firebase_app()
            message = messaging.Message(
                notification=messaging.Notification(
                    title="✅ Compte activé !",
                    body="Votre dossier a été approuvé. Vous pouvez maintenant recevoir des commandes.",
                ),
                token=profile.fcm_token,
            )
            messaging.send(message)
            print(f"[FCM] Notification approbation envoyée à {user.phone}")
        except Exception as e:
            print(f"[FCM] Erreur : {e}")

    # SMS fallback
    if user:
        try:
            from app.services.sms_service import get_sms_service
            sms = get_sms_service()
            sms.send(
                f"Allo Tiak-Tiak : Votre compte a ete approuve ! Vous pouvez maintenant vous connecter et recevoir des commandes.",
                [user.phone]
            )
            print(f"[SMS] Notification approbation envoyee a {user.phone}")
        except Exception as e:
            print(f"[SMS] Erreur : {e}")

    return {"message": "KYC approuve", "user_id": user_id}


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

@router.get("/clients")
def admin_get_clients(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.client_profile import ClientProfile
    users = db.query(User).filter(User.role == "client").all()
    result = []
    for u in users:
        profile = db.query(ClientProfile).filter(ClientProfile.user_id == u.id).first()
        result.append({
            "user_id": u.id,
            "phone": u.phone,
            "full_name": profile.full_name if profile else None,
            "address": profile.address if profile else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return result


@router.delete("/clients/{user_id}")
def admin_delete_client(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.client_profile import ClientProfile
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if profile:
        db.delete(profile)
    db.delete(user)
    db.commit()
    return {"message": "Client supprimé", "user_id": user_id}


@router.get("/monthly")
def admin_monthly_stats(
    month: int,
    year: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from sqlalchemy import extract
    orders = db.query(Order).filter(
        extract('month', Order.created_at) == month,
        extract('year', Order.created_at) == year,
    ).all()

    total_orders = len(orders)
    completed = [o for o in orders if o.status == "confirmed"]
    cancelled = [o for o in orders if o.status == "cancelled"]
    total_revenue = sum(o.amount or 0 for o in completed)
    total_commission = sum(o.commission or 0 for o in completed)
    delivery_orders = [o for o in orders if o.order_type == "delivery"]
    transport_orders = [o for o in orders if o.order_type == "transport"]

    return {
        "month": month,
        "year": year,
        "total_orders": total_orders,
        "completed_orders": len(completed),
        "cancelled_orders": len(cancelled),
        "total_revenue": round(total_revenue, 2),
        "total_commission": round(total_commission, 2),
        "delivery_orders": len(delivery_orders),
        "transport_orders": len(transport_orders),
    }

@router.get("/monthly/rider/{user_id}")
def admin_rider_monthly_stats(
    user_id: int,
    month: int,
    year: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from sqlalchemy import extract
    
    rider = db.query(User).filter(User.id == user_id).first()
    if not rider:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()
    
    orders = db.query(Order).filter(
        Order.rider_id == user_id,
        extract('month', Order.created_at) == month,
        extract('year', Order.created_at) == year,
    ).all()

    completed = [o for o in orders if o.status == "confirmed"]
    cancelled = [o for o in orders if o.status == "cancelled"]
    delivery_orders = [o for o in completed if o.order_type == "delivery"]
    transport_orders = [o for o in completed if o.order_type == "transport"]
    total_revenue = sum(o.amount or 0 for o in completed)
    total_commission = sum(o.commission or 0 for o in completed)
    rider_net = total_revenue - total_commission

    return {
        "rider": {
            "user_id": user_id,
            "phone": rider.phone,
            "full_name": profile.full_name if profile else None,
            "zone": profile.zone if profile else None,
            "services": profile.services if profile else None,
        },
        "month": month,
        "year": year,
        "total_orders": len(orders),
        "completed_orders": len(completed),
        "cancelled_orders": len(cancelled),
        "delivery_orders": len(delivery_orders),
        "transport_orders": len(transport_orders),
        "total_revenue": round(total_revenue, 2),
        "total_commission": round(total_commission, 2),
        "rider_net": round(rider_net, 2),
    }


@router.get("/db/tables")
def admin_db_tables(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from sqlalchemy import text
    tables = ['users', 'rider_profiles', 'client_profiles', 'orders', 'otp_codes', 'rider_locations', 'disputes', 'reviews']
    result = []
    for t in tables:
        count = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        result.append({"table": t, "count": count})
    return result


@router.get("/db/table/{table_name}")
def admin_db_table(
    table_name: str,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from sqlalchemy import text
    allowed = ['users', 'rider_profiles', 'client_profiles', 'orders', 'otp_codes', 'rider_locations', 'disputes', 'reviews']
    if table_name not in allowed:
        raise HTTPException(status_code=400, detail="Table non autorisée")
    offset = (page - 1) * limit
    rows = db.execute(text(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit} OFFSET {offset}")).mappings().all()
    total = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
    return {
        "table": table_name,
        "total": total,
        "page": page,
        "limit": limit,
        "rows": [dict(r) for r in rows]
    }


@router.patch("/db/user/{user_id}/role")
def admin_change_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    if role not in ["client", "rider", "admin"]:
        raise HTTPException(status_code=400, detail="Rôle invalide")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.role = role
    db.commit()
    return {"message": f"Rôle mis à jour", "user_id": user_id, "role": role}


@router.patch("/db/order/{order_id}/status")
def admin_force_order_status(
    order_id: int,
    status: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    allowed = ["pending", "accepted", "in_progress", "delivered", "confirmed", "cancelled", "disputed"]
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Statut invalide")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    order.status = status
    db.commit()
    return {"message": f"Statut mis à jour", "order_id": order_id, "status": status}


@router.patch("/db/rider/{user_id}/availability")
def admin_force_rider_availability(
    user_id: int,
    is_available: bool,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile.is_available = is_available
    db.commit()
    return {"message": "Disponibilité mise à jour", "user_id": user_id, "is_available": is_available}

    
@router.delete("/db/clean/cancelled")
def clean_cancelled_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.price_proposal import PriceProposal
    orders = db.query(Order).filter(Order.status == "cancelled").all()
    count = 0
    for o in orders:
        db.query(PriceProposal).filter(PriceProposal.order_id == o.id).delete()
        db.delete(o)
        count += 1
    db.commit()
    return {"deleted": count, "message": f"{count} commande(s) annulée(s) supprimée(s)"}

@router.delete("/db/clean/expired-pending")
def clean_expired_pending(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.price_proposal import PriceProposal
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    orders = db.query(Order).filter(
        Order.status == "pending",
        Order.created_at < cutoff,
    ).all()
    count = 0
    for o in orders:
        db.query(PriceProposal).filter(PriceProposal.order_id == o.id).delete()
        db.delete(o)
        count += 1
    db.commit()
    return {"deleted": count, "message": f"{count} commande(s) expirée(s) supprimée(s)"}

@router.delete("/db/clean/orphan-proposals")
def clean_orphan_proposals(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.price_proposal import PriceProposal
    result = db.query(PriceProposal).filter(
        PriceProposal.status.in_(["rejected", "accepted"]),
    ).delete()
    db.commit()
    return {"deleted": result, "message": f"{result} proposition(s) supprimée(s)"}

@router.delete("/db/clean/test-orders")
def clean_test_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.price_proposal import PriceProposal
    orders = db.query(Order).filter(
        Order.status.notin_(["confirmed"])
    ).all()
    count = 0
    for o in orders:
        db.query(PriceProposal).filter(PriceProposal.order_id == o.id).delete()
        db.delete(o)
        count += 1
    db.commit()
    return {"deleted": count, "message": f"{count} commande(s) supprimée(s)"}

@router.patch("/orders/{order_id}/assign-rider")
def admin_assign_rider(
    order_id: int,
    rider_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    from app.models.rider_profile import RiderProfile
    rider = db.query(RiderProfile).filter(RiderProfile.user_id == rider_id).first()
    if not rider:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    order.rider_id = rider_id
    order.status = "accepted"
    from datetime import datetime, timezone
    order.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Livreur #{rider_id} assigne a la commande #{order_id}"}
