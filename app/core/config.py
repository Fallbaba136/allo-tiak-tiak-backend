from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Africa's Talking SMS
    AT_USERNAME: str = "sandbox"
    AT_API_KEY: str = ""

    # Environnement
    ENV: str = "dev"

    # Database
    DATABASE_URL: str = "postgresql://postgres:Bbff2030@192.168.1.34:5432/allo_tiak_tiak"

    # JWT
    JWT_SECRET: str = ""
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 60
    ADMIN_SECRET: str = ""

    # OTP
    OTP_TTL_MINUTES: int = 10

    # Firebase (JSON stringifié)
    FIREBASE_CREDENTIALS_JSON: str = ""

    @field_validator("JWT_SECRET", "ADMIN_SECRET")
    @classmethod
    def must_not_be_empty(cls, v: str, info) -> str:
        if not v:
            raise ValueError(f"{info.field_name} ne peut pas être vide")
        return v

    @property
    def DEV(self) -> bool:
        return self.ENV.lower() == "dev"

settings = Settings()