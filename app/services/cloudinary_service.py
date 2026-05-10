import cloudinary
import cloudinary.uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

def upload_kyc_document(file_bytes: bytes, folder: str, public_id: str) -> str:
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=f"allo-tiak-tiak/kyc/{folder}",
        public_id=public_id,
        resource_type="image",
        overwrite=True,
    )
    return result["secure_url"]