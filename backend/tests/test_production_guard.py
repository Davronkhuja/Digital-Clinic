"""Production'da zaif/standart sirlar bilan ishga tushmaslik (v2.1.1) va .env.example to'liqligi."""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, weak_secret
from app.services import messaging

GOOD = dict(jwt_secret="9f2c4b7a1e8d3c6b5a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b",
            database_url="postgresql+psycopg://clinic:5b1d0e7c9a3f4826b0c1d2e3f4a5b6c7@db:5432/clinic",
            APP_ENV="production", sms_backend="disabled", cors_origins="https://klinika.example.org", public_base_url="https://klinika.example.org",
            admin_password="Zk8!vN2#qL5@xR9wT", seed_demo=False)


def make(**kw) -> Settings:
    return Settings(_env_file=None, **{**GOOD, **kw})


def test_good_production_settings_start():
    s = make()
    assert s.is_production and s.sms_backend == "disabled"


@pytest.mark.parametrize("override,needle", [
    ({"jwt_secret": "changeme" * 5}, "JWT_SECRET"),
    ({"jwt_secret": "a" * 40}, "JWT_SECRET"),
    ({"database_url": "postgresql+psycopg://clinic:clinic@db:5432/clinic"}, "POSTGRES_PASSWORD"),
    ({"database_url": "postgresql+psycopg://clinic:postgres12345@db:5432/clinic"}, "POSTGRES_PASSWORD"),
    ({"database_url": "postgresql+psycopg://clinic@db:5432/clinic"}, "POSTGRES_PASSWORD"),
    ({"admin_password": "password123"}, "ADMIN_PASSWORD"),
    ({"admin_password": "Short1!"}, "ADMIN_PASSWORD"),
    ({"seed_demo": True}, "SEED_DEMO"),
    ({"cors_origins": "http://klinika.example.org"}, "CORS_ORIGINS"),
    ({"public_base_url": "http://localhost:5180"}, "PUBLIC_BASE_URL"),
    ({"sms_backend": "mock"}, "SMS_BACKEND"),
])
def test_weak_or_default_secrets_refuse_to_start_in_production(override, needle):
    with pytest.raises(ValidationError) as err:
        make(**override)
    assert needle in str(err.value)


def test_all_problems_reported_together():
    with pytest.raises(ValidationError) as err:
        make(jwt_secret="changeme" * 5, seed_demo=True, admin_password="password123")
    msg = str(err.value)
    assert "JWT_SECRET" in msg and "SEED_DEMO" in msg and "ADMIN_PASSWORD" in msg


def test_dev_and_test_environments_are_not_restricted():
    s = Settings(_env_file=None, jwt_secret="x" * 32, database_url="postgresql+psycopg://clinic:clinic@db/clinic", APP_ENV="development", seed_demo=True)
    assert s.seed_demo and not s.is_production
    assert weak_secret("9f2c4b7a1e8d3c6b5a0f9e8d7c6b5a4f", 32) is None


def test_disabled_sms_adapter_and_otp_endpoint(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "sms_backend", "disabled")
    messaging._adapters.clear()
    try:
        with pytest.raises(messaging.SendError):
            messaging.get_adapter(messaging.Channel.sms).send("+998901234567", "x")
        res = client.post("/public/otp/request", json={"phone": "+998 90 123 45 67", "purpose": "booking"})
        assert res.status_code == 503 and "SMS xizmati sozlanmagan" in res.json()["detail"]
    finally:
        messaging._adapters.clear()


def test_env_example_lists_every_setting():
    """Har bir sozlama (Settings maydoni) .env.example da bo'lishi shart: yangi o'zgaruvchi qo'shsangiz, shu yerga ham yozing."""
    root = Path(__file__).resolve().parents[2] / ".env.example"
    if not root.exists():
        pytest.skip(".env.example konteynerda yo'q (faqat repoda tekshiriladi)")
    text = root.read_text()
    listed = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, re.M))
    internal = {"DATABASE_URL", "JWT_ALGORITHM", "BCRYPT_ROUNDS", "ENV"}        # DATABASE_URL compose'da yig'iladi; qolgani ichki
    missing = sorted(n.upper() for n in Settings.model_fields if n.upper() not in listed and n.upper() not in internal)
    assert not missing, f".env.example da yo'q: {missing}"
