from pydantic import BaseModel

class RiderUpsert(BaseModel):
    full_name: str | None = None
    zone: str | None = None
    payment_provider: str | None = None
    payment_phone: str | None = None

class RiderOut(BaseModel):
    phone: str
    full_name: str | None
    zone: str | None
    payment_provider: str | None
    payment_phone: str | None
    is_available: bool
    is_verified: bool
