from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
#import models so alembic can discover them
from app.models.user import User #noqa: F401
from app.models.rider_profile import RiderProfile # noqa: F401
from app.models.otp_code import OTPCode #noqa: F401 
from app.models.client_profile import ClientProfile # noqa: F401  ✅ ajouté
from app.models.order import Order # noqa: F401