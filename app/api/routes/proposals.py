from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.models.price_proposal import PriceProposal
from app.models.rider_profile import RiderProfile
from app.models.review import Review
from app.api.dependencies import get_current_user
from app.services.notification_service import send_order_notification

router = APIRouter()

@router.post("/orders/{order_id}/propose-price")
def propose_price(
    order_id: int,
    proposed_price: float,
    current_location: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Reserve aux livreurs")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile or not profile.is_verified or profile.is_blocked:
        raise HTTPException(status_code=403, detail="Profil non autorise")

    if not profile.is_available:
        raise HTTPException(status_code=403, detail="Vous devez etre disponible")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Cette commande n'est plus disponible")

    existing = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.rider_id == current_user.id,
    ).first()
    if existing:
        existing.proposed_price = proposed_price
        db.commit()
        return {"message": "Proposition mise a jour", "proposed_price": proposed_price}

    proposal = PriceProposal(
        order_id=order_id,
        rider_id=current_user.id,
        proposed_price=proposed_price,
        current_location=current_location,
        status="pending",
    )
    db.add(proposal)
    db.commit()

    # Notifier le client via FCM
    from app.models.client_profile import ClientProfile
    client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
    if client_profile and hasattr(client_profile, 'fcm_token') and client_profile.fcm_token:
        try:
            send_order_notification(
                fcm_token=client_profile.fcm_token,
                order_id=order_id,
                pickup=f"Nouveau prix propose: {proposed_price} FCFA",
                dropoff=profile.full_name or "Un livreur",
            )
        except Exception as e:
            print(f"[FCM] Erreur notification client: {e}")

    return {"message": "Proposition envoyee", "proposed_price": proposed_price}


@router.get("/orders/{order_id}/proposals")
def get_proposals(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if order.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce n'est pas votre commande")

    proposals = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.status == "pending",
    ).all()

    result = []
    for p in proposals:
        rider = db.query(User).filter(User.id == p.rider_id).first()
        rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == p.rider_id).first()
        rating_data = db.query(func.avg(Review.rating).label("avg_rating"), func.count(Review.id).label("total")).filter(Review.rider_id == p.rider_id).first()
        result.append({
            "proposal_id": p.id,
            "rider_id": p.rider_id,
            "rider_name": rider_profile.full_name if rider_profile else None,
            "rider_phone": rider.phone if rider else None,
            "rider_zone": rider_profile.zone if rider_profile else None,
            "rider_avatar": rider_profile.avatar_url if rider_profile else None,
            "rider_services": rider_profile.services if rider_profile else None,
            "rider_rating": round(float(rating_data.avg_rating), 1) if rating_data.avg_rating else None,
            "rider_rating_count": rating_data.total or 0,
            "proposed_price": p.proposed_price,
            "current_location": p.current_location,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return sorted(result, key=lambda x: x["proposed_price"])


@router.post("/orders/{order_id}/accept-proposal/{proposal_id}")
def accept_proposal(
    order_id: int,
    proposal_id: int,
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
        raise HTTPException(status_code=400, detail="Commande non disponible")

    proposal = db.query(PriceProposal).filter(
        PriceProposal.id == proposal_id,
        PriceProposal.order_id == order_id,
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable")

    now = datetime.now(timezone.utc)
    order.rider_id = proposal.rider_id
    order.amount = proposal.proposed_price
    order.status = "accepted"
    order.accepted_at = now
    if order.order_type == "delivery":
            import secrets
            from time import time
            code = f"{secrets.randbelow(10**6):06d}"
            order.delivery_code = code
            order.delivery_code_expires_at = int(time()) + 60 * 60 * 24
            try:
                from app.services.sms_service import send_delivery_code_sms
                send_delivery_code_sms(
                    receiver_phone=order.receiver_phone,
                    code=code,
                    order_id=order.id,
                )
            except Exception as sms_err:
                print(f"[SMS] Erreur envoi code : {sms_err}")

    # Rejeter les autres propositions
    db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.id != proposal_id,
    ).update({"status": "rejected"})

    db.commit()

    # Notifier les livreurs rejetés
    rejected_proposals = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.id != proposal_id,
    ).all()
    
    for rp in rejected_proposals:
        rejected_profile = db.query(RiderProfile).filter(RiderProfile.user_id == rp.rider_id).first()
        if rejected_profile and rejected_profile.fcm_token:
            try:
                send_order_notification(
                    fcm_token=rejected_profile.fcm_token,
                    order_id=order_id,
                    pickup="Commande attribuee a un autre livreur",
                    dropoff="Votre offre n'a pas ete retenue",
                )
            except Exception as e:
                print(f"[FCM] Erreur notification rejet: {e}")

    # Notifier le livreur choisi
    rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == proposal.rider_id).first()
    if rider_profile and rider_profile.fcm_token:
        try:
            from app.services.notification_service import send_notification
            send_notification(
                fcm_token=rider_profile.fcm_token,
                title="✅ Offre acceptée !",
                body=f"Le client a accepté votre offre de {int(proposal.proposed_price):,} FCFA. Rendez-vous au point de départ !",
                data={"order_id": str(order_id), "type": "proposal_accepted"}
            )
        except Exception as e:
            print(f"[NOTIF] Erreur notification livreur: {e}")

    # Notifier le client avec ETA
    try:
        from app.models.client_profile import ClientProfile
        from app.services.notification_service import send_rider_accepted_notification
        client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == order.client_id).first()
        rider_profile_notif = db.query(RiderProfile).filter(RiderProfile.user_id == proposal.rider_id).first()
        if client_profile and client_profile.fcm_token:
            send_rider_accepted_notification(
                client_fcm_token=client_profile.fcm_token,
                order_id=order_id,
                rider_name=rider_profile_notif.full_name if rider_profile_notif else None,
                rider_lat=rider_profile_notif.current_lat if rider_profile_notif else None,
                rider_lng=rider_profile_notif.current_lng if rider_profile_notif else None,
            )
    except Exception as e:
        print(f"[NOTIF] Erreur notif client : {e}")
    print(f"[ACCEPT] Proposition {proposal_id} acceptee pour commande {order_id}")
    print(f"[ACCEPT] OK - order {order_id}, proposal {proposal_id}, rider {proposal.rider_id}")
    return {"message": "Proposition acceptee", "order_id": order_id, "amount": proposal.proposed_price}



@router.get("/my-proposals")
def get_my_proposals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Reserve aux livreurs")
    
    proposals = db.query(PriceProposal).filter(
        PriceProposal.rider_id == current_user.id,
        PriceProposal.status == "pending",
    ).all()
    
    return [{"order_id": p.order_id, "proposed_price": p.proposed_price} for p in proposals]
@router.get("/orders/{order_id}/proposals-admin")
def get_proposals_admin(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposals = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
    ).all()

    result = []
    for p in proposals:
        rider = db.query(User).filter(User.id == p.rider_id).first()
        rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == p.rider_id).first()
        result.append({
            "proposal_id": p.id,
            "rider_id": p.rider_id,
            "rider_name": rider_profile.full_name if rider_profile else None,
            "rider_phone": rider.phone if rider else None,
            "proposed_price": p.proposed_price,
            "current_location": p.current_location,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return sorted(result, key=lambda x: x["proposed_price"])

@router.post("/orders/{order_id}/counter-propose")
def counter_propose(
    order_id: int,
    counter_price: float,
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
        raise HTTPException(status_code=400, detail="Commande non disponible")

    # Sauvegarder le contre-prix
    from datetime import datetime, timezone
    order.counter_price = counter_price
    order.counter_price_at = datetime.now(timezone.utc)
    db.commit()

    # Notifier tous les livreurs qui ont proposé
    proposals = db.query(PriceProposal).filter(
        PriceProposal.order_id == order_id,
        PriceProposal.status == "pending",
    ).all()

    for p in proposals:
        rider_profile = db.query(RiderProfile).filter(RiderProfile.user_id == p.rider_id).first()
        if rider_profile and rider_profile.fcm_token:
            try:
                send_order_notification(
                    fcm_token=rider_profile.fcm_token,
                    order_id=order_id,
                    pickup=f"Contre-proposition: {counter_price} FCFA",
                    dropoff=f"Le client propose {counter_price} FCFA",
                )
            except Exception as e:
                print(f"[FCM] Erreur: {e}")

    return {"message": "Contre-proposition envoyee", "counter_price": counter_price}
