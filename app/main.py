from fastapi import FastAPI
from app.db.session import engine
from app.db.base import Base

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.riders import router as riders_router

# import models for table creation
from app.models.user import User  # noqa
from app.models.rider_profile import RiderProfile  # noqa
from app.models.otp_code import OTPCode  # noqa

app = FastAPI(title="Allô Tiak-Tiak API", version="0.1.0")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(riders_router, prefix="/riders", tags=["riders"])
