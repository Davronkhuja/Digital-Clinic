from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Ma'lumotlar bazasi (SQLAlchemy URL)
    database_url: str

    # Boshlang'ich ma'lumotlar
    seed_demo: bool = False  # true: faqat bo'sh bazaga demo ma'lumotlar yuklanadi
    admin_email: str = ""  # demo bo'lmasa, birinchi administrator (bo'sh bazada)
    admin_password: str = ""

    # CORS: vergul bilan ajratilgan aniq originlar
    cors_origins: str = "http://localhost:5180"

    # AI
    ai_enabled: bool = False
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.1-8b-instant"
    llm_timeout: float = 30

    @field_validator("jwt_secret")
    @classmethod
    def _secret_long_enough(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET kamida 32 belgi bo'lishi kerak")
        return v

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, v: str) -> str:
        if "*" in [o.strip() for o in v.split(",")]:
            raise ValueError("CORS_ORIGINS ichida '*' ishlatib bo'lmaydi")
        return v

    @field_validator("llm_base_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
