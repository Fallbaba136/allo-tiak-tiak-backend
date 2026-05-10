from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.rider_profile import RiderProfile
from app.api.dependencies import get_current_user
from app.services.cloudinary_service import upload_kyc_document

router = APIRouter()

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/jpg"]
MAX_SIZE = 5 * 1024 * 1024  # 5MB

def validate_file(file: UploadFile):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Format invalide. JPG ou PNG uniquement.")

@router.post("/upload")
async def upload_kyc_documents(
    cni_front: UploadFile = File(...),
    cni_back: UploadFile = File(...),
    selfie: UploadFile = File(...),
    permis: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Réservé aux livreurs")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil livreur introuvable")

    if profile.kyc_status == "approved":
        raise HTTPException(status_code=400, detail="KYC déjà approuvé")

    for f in [cni_front, cni_back, selfie, permis]:
        validate_file(f)

    uid = str(current_user.id)

    cni_front_bytes = await cni_front.read()
    cni_back_bytes = await cni_back.read()
    selfie_bytes = await selfie.read()
    permis_bytes = await permis.read()

    profile.cni_front_url = upload_kyc_document(cni_front_bytes, "cni_front", f"rider_{uid}_cni_front")
    profile.cni_back_url = upload_kyc_document(cni_back_bytes, "cni_back", f"rider_{uid}_cni_back")
    profile.selfie_url = upload_kyc_document(selfie_bytes, "selfie", f"rider_{uid}_selfie")
    profile.permis_url = upload_kyc_document(permis_bytes, "permis", f"rider_{uid}_permis")
    profile.kyc_status = "submitted"

    db.commit()

    return {"message": "Documents soumis avec succès", "kyc_status": "submitted"}


@router.get("/status")
def get_kyc_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "rider":
        raise HTTPException(status_code=403, detail="Réservé aux livreurs")

    profile = db.query(RiderProfile).filter(RiderProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil livreur introuvable")

    return {
        "kyc_status": profile.kyc_status,
        "is_blocked": profile.is_blocked,
        "rejection_reason": profile.kyc_rejection_reason,
    }