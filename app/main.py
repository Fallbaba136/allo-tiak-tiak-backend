from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import engine
from app.db.base import Base

from app.modules.auth.router import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.riders import router as riders_router
from app.api.routes.clients import router as clients_router
from app.api.routes.orders import router as orders_router
from app.models.rider_location import RiderLocation  # noqa
from app.api.routes.location import router as location_router
from app.models.dispute import Dispute  # noqa
from app.api.routes.disputes import router as disputes_router
from app.api.routes.reviews import router as reviews_router
from app.models.user import User  # noqa
from app.models.rider_profile import RiderProfile  # noqa
from app.models.otp_code import OTPCode  # noqa
from app.models.client_profile import ClientProfile  # noqa
from app.models.order import Order  # noqa
from app.models.review import Review  # noqa
from app.api.routes.stats import router as stats_router
from app.api.routes.admin import router as admin_router
from app.api.routes.kyc import router as kyc_router
from app.api.routes.proposals import router as proposals_router
from app.api.routes.messages import router as messages_router


app = FastAPI(title="Allô Tiak-Tiak API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(riders_router, prefix="/riders", tags=["riders"])
app.include_router(clients_router, prefix="/clients", tags=["clients"])
app.include_router(orders_router, prefix="/orders", tags=["orders"])
app.include_router(location_router, prefix="/location", tags=["location"])
app.include_router(disputes_router, prefix="/disputes", tags=["disputes"])
app.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
app.include_router(stats_router, prefix="/stats", tags=["stats"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(kyc_router, prefix="/kyc", tags=["kyc"])
app.include_router(proposals_router, tags=["proposals"])
app.include_router(messages_router, tags=["messages"])