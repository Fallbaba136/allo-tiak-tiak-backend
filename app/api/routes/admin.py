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
            "client_response": d.client_response,
            "rider_response": d.rider_response,
            "resolution_favor": d.resolution_favor,
            "dispute_type": d.dispute_type,
            "client_response_at": d.client_response_at.isoformat() if d.client_response_at else None,
            "rider_response_at": d.rider_response_at.isoformat() if d.rider_response_at else None,
            "order_traces": get_order_traces(d.order_id, db),
        })
    return result

def get_order_traces(order_id, db):
    from app.models.order import Order
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    return {
        "id": order.id,
        "amount": order.amount,
        "status": order.status,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
        "picked_up_at": order.picked_up_at.isoformat() if order.picked_up_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "payment_confirmed_at": order.payment_confirmed_at.isoformat() if order.payment_confirmed_at else None,
        "delivery_code_used": order.delivery_code is None and order.status in ['confirmed'],
        "pickup_address": order.pickup_address,
        "delivery_address": order.delivery_address,
        "cancellation_reason": order.cancellation_reason,
    }

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

@router.get("/stats/finance")
def admin_finance_stats(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def get_stats(start):
        result = db.query(
            func.count(Order.id).label('count'),
            func.sum(Order.amount).label('total_amount'),
            func.sum(Order.commission).label('total_commission'),
        ).filter(
            Order.status == 'confirmed',
            Order.confirmed_at >= start,
        ).first()
        return {
            'count': result.count or 0,
            'total_amount': float(result.total_amount or 0),
            'total_commission': float(result.total_commission or 0),
        }

    return {
        'today': get_stats(start_of_today),
        'week': get_stats(start_of_week),
        'month': get_stats(start_of_month),
        'all_time': get_stats(datetime(2020, 1, 1, tzinfo=timezone.utc)),
    }

@router.get("/users/{user_id}/details")
def admin_get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.client_profile import ClientProfile
    from app.models.rider_profile import RiderProfile
    from app.models.review import Review
    from sqlalchemy import func

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == user_id).first()
    rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == user_id).first()

    # Commandes
    if user.role == 'client':
        orders = db.query(Order).filter(Order.client_id == user_id).order_by(Order.created_at.desc()).limit(20).all()
    else:
        orders = db.query(Order).filter(Order.rider_id == user_id).order_by(Order.created_at.desc()).limit(20).all()

    # Stats
    confirmed = [o for o in orders if o.status == 'confirmed']
    cancelled = [o for o in orders if o.status == 'cancelled']

    # Notes
    rating_data = db.query(
        func.avg(Review.rating).label('avg'),
        func.count(Review.id).label('total'),
    ).filter(Review.rider_id == user_id).first()

    return {
        'user_id': user_id,
        'phone': user.phone,
        'role': user.role,
        'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None,
        'client_name': client_profile.full_name if client_profile else None,
        'client_address': client_profile.address if client_profile else None,
        'rider_name': rider_profile.full_name if rider_profile else None,
        'rider_zone': rider_profile.zone if rider_profile else None,
        'rider_is_verified': rider_profile.is_verified if rider_profile else None,
        'rider_is_blocked': rider_profile.is_blocked if rider_profile else None,
        'total_orders': len(orders),
        'confirmed_orders': len(confirmed),
        'cancelled_orders': len(cancelled),
        'total_spent': sum(o.amount or 0 for o in confirmed) if user.role == 'client' else 0,
        'total_earned': sum((o.amount or 0) * 0.95 for o in confirmed) if user.role == 'rider' else 0,
        'average_rating': round(float(rating_data.avg), 1) if rating_data.avg else None,
        'total_reviews': rating_data.total or 0,
        'recent_orders': [
            {
                'id': o.id,
                'status': o.status,
                'amount': o.amount,
                'order_type': o.order_type,
                'created_at': o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders[:10]
        ],
    }

@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.client_profile import ClientProfile
    from app.models.rider_profile import RiderProfile

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    db.query(ClientProfile).filter(ClientProfile.user_id == user_id).delete()
    db.query(RiderProfile).filter(RiderProfile.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur #{user_id} supprime"}

@router.delete("/cleanup/expired-orders")
def cleanup_expired_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from datetime import datetime, timezone, timedelta
    from app.models.price_proposal import PriceProposal

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    expired = db.query(Order).filter(
        Order.status == "pending",
        Order.created_at < cutoff,
    ).all()

    count = 0
    for o in expired:
        db.query(PriceProposal).filter(PriceProposal.order_id == o.id).delete()
        db.delete(o)
        count += 1

    db.commit()
    print(f"[CLEANUP] {count} commandes expirees supprimees")
    return {"deleted": count, "message": f"{count} commandes supprimees"}

@router.get("/cron/cleanup")
def cron_cleanup(
    secret: str,
    db: Session = Depends(get_db),
):
    from app.core.config import settings
    if secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Acces refuse")

    from datetime import datetime, timezone, timedelta
    from app.models.price_proposal import PriceProposal

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    expired = db.query(Order).filter(
        Order.status == "pending",
        Order.created_at < cutoff,
    ).all()

    count = 0
    for o in expired:
        db.query(PriceProposal).filter(PriceProposal.order_id == o.id).delete()
        db.delete(o)
        count += 1

    db.commit()
    print(f"[CRON] {count} commandes expirees supprimees")
    return {"deleted": count}

@router.patch("/disputes/{dispute_id}/admin-resolve")
def admin_resolve_dispute_full(
    dispute_id: int,
    resolution_note: str,
    resolution_favor: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.dispute import Dispute
    from app.models.order import Order
    from app.models.client_profile import ClientProfile
    from app.models.rider_profile import RiderProfile
    from app.services.notification_service import send_notification

    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Litige introuvable")

    dispute.status = "resolved"
    dispute.resolution_note = resolution_note
    dispute.resolution_favor = resolution_favor
    db.commit()

    # Notifier les deux parties
    try:
        order = db.query(Order).filter(Order.id == dispute.order_id).first()
        if order:
            favor_client = resolution_favor == 'client'
            # Notifier client
            client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
            if client_profile and client_profile.fcm_token:
                send_notification(
                    fcm_token=client_profile.fcm_token,
                    title="⚖️ Litige résolu",
                    body=f"{'✅ Decision en votre faveur' if favor_client else '❌ Decision en faveur du livreur'}. {resolution_note}",
                    data={"dispute_id": str(dispute_id), "type": "dispute_resolved"}
                )
            # Notifier livreur
            rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == order.rider_id).first()
            if rider_profile and rider_profile.fcm_token:
                send_notification(
                    fcm_token=rider_profile.fcm_token,
                    title="⚖️ Litige résolu",
                    body=f"{'❌ Decision en faveur du client' if favor_client else '✅ Decision en votre faveur'}. {resolution_note}",
                    data={"dispute_id": str(dispute_id), "type": "dispute_resolved"}
                )
    except Exception as e:
        print(f"[NOTIF] Erreur : {e}")

    return {"message": "Litige resolu"}

@router.get("/audit-logs/{order_id}")
def get_audit_logs(
    order_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    from app.models.audit_log import AuditLog
    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == "order",
        AuditLog.entity_id == order_id
    ).order_by(AuditLog.created_at.asc()).all()
    result = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first()
        result.append({
            "id": log.id,
            "action": log.action,
            "user_phone": user.phone if user else None,
            "user_role": user.role if user else None,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return result
