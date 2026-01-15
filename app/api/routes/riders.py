from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import get_db
from app.models.user import User
from app.models.rider_profile import RiderProfile
from app.schemas.rider import RiderUpsert, RiderOut
from app.core.config import settings

router = APIRouter()

def get_phone_from_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        return payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token")

@router.put("/me", response_model=RiderOut)
def upsert_my_profile(
    payload: RiderUpsert,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    phone = get_phone_from_token(authorization)

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user.id).first()
    if not profile:
        profile = RiderProfile(user_id=user.id)
        db.add(profile)

    profile.full_name = payload.full_name
    profile.zone = payload.zone
    profile.payment_provider = payload.payment_provider
    profile.payment_phone = payload.payment_phone

    db.commit()
    db.refresh(profile)

    return RiderOut(
        phone=user.phone,
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
    authorization: str | None = Header(default=None),
):
    phone = get_phone_from_token(authorization)
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not created yet")

    profile.is_available = is_available
    db.commit()
    return {"ok": True, "is_available": profile.is_available}

@router.get("/available", response_model=list[RiderOut])
def list_available_riders(zone: str | None = None, db: Session = Depends(get_db)):
    q = db.query(User, RiderProfile).join(RiderProfile, RiderProfile.user_id == User.id)
    q = q.filter(RiderProfile.is_available == True)  # noqa: E712
    if zone:
        q = q.filter(RiderProfile.zone.ilike(zone))

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
