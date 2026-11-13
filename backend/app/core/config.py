from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    bcrypt_rounds: int = 12  # testlarda kamaytiriladi
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Ma'lumotlar bazasi (SQLAlchemy URL)
    database_url: str

    # Boshlang'ich ma'lumotlar
    seed_demo: bool = False  # true: faqat bo'sh bazaga demo ma'lumotlar yuklanadi
    admin_email: str = ""  # demo bo'lmasa, birinchi administrator (bo'sh bazada)
    admin_password: str = ""

    # Mijoz IP'sini X-Forwarded-For'dan olishga ishonchli proksilar (vergul bilan, CIDR); docker tarmog'i standarti
    trusted_proxies: str = "127.0.0.1/32,::1/128,172.16.0.0/12,10.0.0.0/8"

    # CORS: vergul bilan ajratilgan aniq originlar
    cors_origins: str = "http://localhost:5180"

    # Fayl saqlash (EMR ilovalari): storage interfeysi orqali; hozircha lokal (docker volume), keyin S3/MinIO
    storage_backend: str = "local"
    storage_dir: str = "/data/uploads"
    max_upload_mb: int = 20

    # Fiskal chek (virtual kassa): hozircha faqat mock. Real adapter uchun operator hujjatlari va kalitlar kerak
    fiscal_backend: str = "mock"

    # Payme Merchant API (kalitlar faqat .env da). Bo'sh kalit: Payme endpoint hamma so'rovni rad etadi.
    # payme_test_mode=true: sandbox (PAYME_TEST_KEY, test checkout); productionda false va PAYME_KEY
    payme_merchant_id: str = ""
    payme_key: str = ""
    payme_test_key: str = ""
    payme_test_mode: bool = True
    payme_units_code: int = 796  # chek qatorida o'lchov birligi kodi (taxmin: 796 = dona); Payme hujjatidagi klassifikatordan tasdiqlang

    # Click SHOP API (kalitlar faqat .env da). Bo'sh maxfiy kalit: Click endpoint hamma so'rovni rad etadi (sign check failed).
    # click_test_mode=true: sandbox (CLICK_TEST_SECRET_KEY); productionda false va CLICK_SECRET_KEY
    click_service_id: str = ""
    click_merchant_id: str = ""
    click_secret_key: str = ""
    click_test_secret_key: str = ""
    click_test_mode: bool = True

    # Xabarlar (4-bosqich): Redis + Celery, SMS adapteri (hozircha mock), Telegram bot (token faqat .env da)
    redis_url: str = "redis://redis:6379/0"
    public_base_url: str = "http://localhost:5180"  # xabardagi havolalar (tasdiqlash, onlayn yozilish) uchun
    # Muhit: development | test | production (`APP_ENV` yoki `ENV`). Production'da mock SMS taqiqlangan (backend ishga tushmaydi).
    app_env: str = Field("development", validation_alias=AliasChoices("APP_ENV", "ENV"))
    sms_backend: str = "mock"
    # Faqat dev/test: mock SMS matnlari (OTP shu yerda) JSON-qator ko'rinishida shu faylga yoziladi. Oddiy jurnalga hech qachon yozilmaydi.
    mock_sms_outbox: str = ""
    telegram_bot_token: str = ""
    link_secret: str = ""  # imzolangan havolalar kaliti; bo'sh bo'lsa jwt_secret dan olinadi

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

    @model_validator(mode="after")
    def _no_mock_sms_in_production(self):
        if self.app_env.strip().lower() == "production":
            if self.sms_backend == "mock":
                raise ValueError("Production'da SMS_BACKEND=mock taqiqlangan: haqiqiy SMS provayderini sozlang")
            if self.mock_sms_outbox:
                raise ValueError("Production'da MOCK_SMS_OUTBOX ishlatib bo'lmaydi")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

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
