import secrets
from time import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.security import hash_code, verify_code, create_access_token
from app.models.user import User
from app.models.otp_code import OTPCode
from app.schemas.auth import OTPStartRequest, OTPVerifyRequest, TokenResponse

router = APIRouter()

@router.post("/otp/start")
def otp_start(payload: OTPStartRequest, db: Session = Depends(get_db)):
    phone = payload.phone.strip()
    
    #Cleanup expired OTPs (MVP)
    now_ts = int(time())
    db.query(OTPCode).filter(OTPCode.expires_at_ts < now_ts).delete()
    db.commit()
    
    #MVP rate-limit: 1 OPT per phone per 60 seconds
    latest = (
        db.query(OTPCode)
        .filter(OTPCode.phone == phone)
        .order_by(OTPCode.created_at.desc())
        .first()
     )
    if latest and (int(time()) - (latest.expires_at_ts - settings.OTP_TTL_MINUTES * 60)) < 60:
       raise HTTPException(status_code=429, detail="Trop de demandes. Réessayez dans 60s.")

    # Generate 6-digit OTP (MVP)
    code = f"{secrets.randbelow(10**6):06d}"
    code_h = hash_code(code)

    # Store expiration as epoch seconds (SQLite friendly)
    expires_ts = int(time()) + settings.OTP_TTL_MINUTES * 60

    db.add(OTPCode(phone=phone, code_hash=code_h, expires_at_ts=expires_ts))
    db.commit()

    # MVP ONLY: return OTP for testing (replace by SMS later)
    resp = {
        "message": "OTP generated (MVP).",
        "expires_in_minutes": settings.OTP_TTL_MINUTES,
    }
    if settings.DEV:
        resp["otp_for_test"] = code
    return resp

@router.post("/otp/verify", response_model=TokenResponse)
def otp_verify(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    phone = payload.phone.strip()
    code = payload.code.strip()

    otp = (
        db.query(OTPCode)
        .filter(OTPCode.phone == phone)
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=400, detail="OTP not found")

    if otp.expires_at_ts < int(time()):
        raise HTTPException(status_code=400, detail="OTP expired")

    if not verify_code(code, otp.code_hash):
        raise HTTPException(status_code=400, detail="Invalid code")

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone, is_phone_verified=True, role="rider")
        db.add(user)
    else:
        user.is_phone_verified = True

    db.commit()

    token = create_access_token(sub=phone)
    return TokenResponse(access_token=token)
