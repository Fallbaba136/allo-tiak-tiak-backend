from pydantic import BaseModel
from typing import Literal

class RiderUpsert(BaseModel):
    full_name: str | None = None
    zone: str | None = None
    payment_provider: str | None = None
    payment_phone: str | None = None
    services: Literal["delivery", "transport", "delivery,transport"] = "delivery"
    pricing: str | None = None  # JSON string ex: {"Plateau→Almadies": 2000}

class RiderOut(BaseModel):
    phone: str
    full_name: str | None
    zone: str | None
    payment_provider: str | None
    payment_phone: str | None
    is_available: bool
    is_verified: bool
    services: str
    pricing: str | None = None

class FCMTokenUpdate(BaseModel):
    fcm_token: str