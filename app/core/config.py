from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", extra="ignore")

	#environnment
	ENV: str = "dev"

	#Database
	DATABASE_URL: str = "sqlite:///./allo_tiak_tiak.db"

	#JWT
	JWT_SECRET: str = "CHANGE_ME_SUPER_SECRET"
	JWT_ALG: str = "HS256"
	ACCESS_TOKEN_MINUTES: int = 60

	#OPT
	OTP_TTL_MINUTES: int = 10
	
	#DEV mode (auto)
	@property
	def DEV(self) -> bool:
		return self.ENV.lower() == "dev"


settings = Settings()
