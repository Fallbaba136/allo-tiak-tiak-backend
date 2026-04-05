from pydantic import BaseModel

class ClientUpsert(BaseModel):
    full_name: str | None = None
    address: str | None = None

class ClientOut(BaseModel):
    phone: str
    full_name: str | None
    address: str | None