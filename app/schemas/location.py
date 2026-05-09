from pydantic import BaseModel
from datetime import datetime

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    order_id: int | None = None

class LocationOut(BaseModel):
    rider_id: int
    latitude: float
    longitude: float
    order_id: int | None
    updated_at: datetime