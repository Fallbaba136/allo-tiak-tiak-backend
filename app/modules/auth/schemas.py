from pydantic import BaseModel
from typing import Literal

class OTPStartRequest(BaseModel):
    phone: str

class OTPVerifyRequest(BaseModel):
    phone: str
    code: str
    role: Literal["client", "rider"] = "client"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
