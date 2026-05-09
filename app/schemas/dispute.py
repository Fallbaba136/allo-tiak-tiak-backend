from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class DisputeCreate(BaseModel):
    order_id: int
    reason: str
    description: str

class DisputeOut(BaseModel):
    id: int
    complainant_id: int
    accused_id: int
    order_id: int
    reason: str
    description: str
    status: str
    resolution_note: str | None
    expires_at: datetime
    created_at: datetime

class DisputeResolve(BaseModel):
    status: Literal["resolved", "rejected"]
    resolution_note: str