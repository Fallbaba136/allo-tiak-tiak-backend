from datetime import datetime, timedelta, timezone
from jose import jwt
from app.core.config import settings
import hashlib
import hmac

def hash_code(code: str) -> str:
    # HMAC-SHA256(code, secret) => stable et safe pour OTP
    code_bytes = code.encode("utf-8")
    secret_bytes = settings.JWT_SECRET.encode("utf-8")
    return hmac.new(secret_bytes, code_bytes, hashlib.sha256).hexdigest()

def verify_code(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_code(code), code_hash)

def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
