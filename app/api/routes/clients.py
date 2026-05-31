from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.client_profile import ClientProfile
from app.schemas.client import ClientUpsert, ClientOut
from app.api.dependencies import get_current_user

router = APIRouter()

@router.get("/me", response_model=ClientOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return ClientOut(
        phone=current_user.phone,
        full_name=profile.full_name,
        address=profile.address,
    )

@router.put("/me", response_model=ClientOut)
def upsert_my_profile(
    payload: ClientUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    if not profile:
        profile = ClientProfile(user_id=current_user.id)
        db.add(profile)

    profile.full_name = payload.full_name
    profile.address = payload.address

    db.commit()
    db.refresh(profile)

    return ClientOut(
        phone=current_user.phone,
        full_name=profile.full_name,
        address=profile.address,
    )

@router.post("/me/fcm-token")
def update_client_fcm_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Reserve aux clients")
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile.fcm_token = token
    db.commit()
    return {"message": "FCM token mis a jour"}