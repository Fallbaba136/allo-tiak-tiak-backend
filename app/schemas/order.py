from pydantic import BaseModel, model_validator
from typing import Literal
from datetime import datetime

class OrderCreate(BaseModel):
    pickup_address: str
    delivery_address: str
    description: str | None = None
    zone: str | None = None
    rider_id: int | None = None  # None = mode auto (broadcast)
    receiver_phone: str | None = None
    amount: float
    order_type: Literal["delivery", "transport"] = "delivery"
    is_urgent: bool = False

    @model_validator(mode="after")
    def check_fields(self):
        if self.order_type == "delivery" and not self.receiver_phone:
            raise ValueError("receiver_phone est obligatoire pour une livraison")
        return self

class OrderOut(BaseModel):
    id: int
    client_id: int
    rider_id: int | None
    pickup_address: str
    delivery_address: str
    description: str | None
    zone: str | None
    receiver_phone: str | None
    status: str
    order_type: str
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
    delivery_photo_url: str | None = None
    is_urgent: bool = False
    broadcast_expires_at: int | None = None
    client_name: str | None = None
    counter_price: float | None = None
    cancellation_reason: str | None = None
    client_phone: str | None = None
    client_address: str | None = None

class OrderStatusUpdate(BaseModel):
    status: Literal["accepted", "in_progress", "delivered", "cancelled", "disputed"]
    cancellation_reason: str | None = None

class DeliveryCodeVerify(BaseModel):
    code: str

class PaymentConfirm(BaseModel):
    payment_method: Literal["wave", "orange_money"]