from pydantic import BaseModel, Field
from datetime import datetime

class ReviewCreate(BaseModel):
    order_id: int
    rating: int = Field(ge=1, le=5)  # entre 1 et 5
    comment: str | None = None

class ReviewOut(BaseModel):
    id: int
    order_id: int
    client_id: int
    rider_id: int
    rating: int
    comment: str | None
    created_at: datetime

class RiderRatingSummary(BaseModel):
    rider_id: int
    average_rating: float
    total_reviews: int
    total_orders: int