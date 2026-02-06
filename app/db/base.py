from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
#import models so alembic can discover them
from app.models.user import User #noqa: F401
from app.models.rider_profile import RiderProfile # noqa: F401
from app.models.otp_code import OTPCode #noqa: F401 
