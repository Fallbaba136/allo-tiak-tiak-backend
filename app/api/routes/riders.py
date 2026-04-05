from fastapi import APIRouter, Depends, HTTPException, Header
from app.api.dependencies import get_current_user
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.rider_profile import RiderProfile
from app.schemas.rider import RiderUpsert, RiderOut
from app.core.config import settings

router = APIRouter()

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

    db.commit()
    db.refresh(profile)

    return RiderOut(
        phone=current_user.phone,
        full_name=profile.full_name,
        zone=profile.zone,
        payment_provider=profile.payment_provider,
        payment_phone=profile.payment_phone,
        is_available=profile.is_available,
        is_verified=profile.is_verified,
    )

@router.post("/me/availability")
def set_availability(
    is_available: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not created yet")

    profile.is_available = is_available
    db.commit()
    return {"ok": True, "is_available": profile.is_available}

@router.get("/available", response_model=list[RiderOut])
def list_available_riders(zone: str | None = None, db: Session = Depends(get_db)):
    q = db.query(User, RiderProfile).join(RiderProfile, RiderProfile.user_id == User.id)

    q = q.filter(RiderProfile.is_available == True)  # noqa: E712
    q = q.filter(RiderProfile.is_verified == True)   # noqa: E712

    if zone:
        q = q.filter(RiderProfile.zone.ilike(f"%{zone}%"))

    rows = q.limit(50).all()

    out: list[RiderOut] = []
    for user, profile in rows:
        out.append(
            RiderOut(
                phone=user.phone,
                full_name=profile.full_name,
                zone=profile.zone,
                payment_provider=profile.payment_provider,
                payment_phone=profile.payment_phone,
                is_available=profile.is_available,
                is_verified=profile.is_verified,
            )
        )
    return out

@router.post("/admin/riders/verify")
def admin_verify_rider(
    phone: str,
    x_admin_secret: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    if not settings.DEV:
        raise HTTPException(status_code=404, detail="Not Found")

    if not x_admin_secret or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Rider profile not found")

    profile.is_verified = True
    db.commit()

    return {"ok": True, "phone": phone, "is_verified": True}