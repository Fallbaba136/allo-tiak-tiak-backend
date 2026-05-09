from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class OrderCreate(BaseModel):
    pickup_address: str
    delivery_address: str
    description: str | None = None
    zone: str | None = None
    rider_id: int
    receiver_phone: str
    amount: float  # montant en FCFA

class OrderOut(BaseModel):
    id: int
    client_id: int
    rider_id: int | None
    pickup_address: str
    delivery_address: str
    description: str | None
    zone: str | None
    receiver_phone: str
    status: str
    amount: float | None
    commission: float | None
    payment_method: str | None
    payment_status: str
    accepted_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    payment_confirmed_at: datetime | None
    created_at: datetime

class OrderStatusUpdate(BaseModel):
    status: Literal["accepted", "in_progress", "delivered", "cancelled", "disputed"]

class DeliveryCodeVerify(BaseModel):
    code: str

class PaymentConfirm(BaseModel):
    payment_method: Literal["wave", "orange_money"]