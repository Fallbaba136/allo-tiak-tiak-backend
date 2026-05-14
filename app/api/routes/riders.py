from fastapi import APIRouter, Depends, HTTPException, Header
from app.api.dependencies import get_current_user
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.rider_profile import RiderProfile
from app.schemas.rider import RiderUpsert, RiderOut, FCMTokenUpdate
from app.core.config import settings

router = APIRouter()

def profile_to_out(user: User, profile: RiderProfile) -> RiderOut:
    return RiderOut(
        phone=user.phone,
        full_name=profile.full_name,
        zone=profile.zone,
        payment_provider=profile.payment_provider,
        payment_phone=profile.payment_phone,
        is_available=profile.is_available,
        is_verified=profile.is_verified,
        services=profile.services,
        pricing=profile.pricing,
    )

@router.post("/me/fcm-token")
def update_fcm_token(
    payload: FCMTokenUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile.fcm_token = payload.fcm_token
    db.commit()
    return {"ok": True, "message": "FCM token enregistré"}

@router.put("/me", response_model=RiderOut)
def upsert_my_profile(
    payload: RiderUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        profile = RiderProfile(user_id=current_user.id)
        db.add(profile)

    profile.full_name = payload.full_name
    profile.zone = payload.zone
    profile.payment_provider = payload.payment_provider
    profile.payment_phone = payload.payment_phone
    profile.services = payload.services
    profile.pricing = payload.pricing

    db.commit()
    db.refresh(profile)
    return profile_to_out(current_user, profile)

@router.get("/me", response_model=RiderOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    return profile_to_out(current_user, profile)

@router.post("/me/availability")
def set_availability(
    is_available: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Profil non créé")
    if profile.is_blocked:
        raise HTTPException(status_code=403, detail="Compte bloqué")
    profile.is_available = is_available
    db.commit()
    return {"ok": True, "is_available": profile.is_available}

@router.get("/available", response_model=list[RiderOut])
def list_available_riders(
    zone: str | None = None,
    service: str | None = None,
    db: Session = Depends(get_db)
):
    q = db.query(User, RiderProfile).join(RiderProfile, RiderProfile.user_id == User.id)
    q = q.filter(RiderProfile.is_available == True)   # noqa: E712
    q = q.filter(RiderProfile.is_verified == True)    # noqa: E712
    q = q.filter(RiderProfile.is_blocked == False)    # noqa: E712

    if zone:
        q = q.filter(RiderProfile.zone.ilike(f"%{zone}%"))

    if service:
        q = q.filter(RiderProfile.services.ilike(f"%{service}%"))

    rows = q.limit(50).all()
    return [profile_to_out(user, profile) for user, profile in rows]

@router.post("/admin/riders/verify")
def admin_verify_rider(
    phone: str,
    x_admin_secret: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    if not x_admin_secret or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil livreur introuvable")

    profile.is_verified = True
    db.commit()
    return {"ok": True, "phone": phone, "is_verified": True}