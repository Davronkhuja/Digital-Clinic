import pytest

from app import seed
from app.core.config import settings
from tests.conftest import truncate_all


def _empty_db_with(monkeypatch, demo: bool, email: str = "", password: str = ""):
    truncate_all()
    monkeypatch.setattr(settings, "seed_demo", demo)
    monkeypatch.setattr(settings, "admin_email", email)
    monkeypatch.setattr(settings, "admin_password", password)


def test_no_demo_and_no_admin_password_refuses_to_start(monkeypatch):
    _empty_db_with(monkeypatch, demo=False)
    with pytest.raises(SystemExit):
        seed.main()


def test_no_demo_with_weak_admin_password_refuses_to_start(monkeypatch):
    _empty_db_with(monkeypatch, demo=False, email="boss@clinic.uz", password="short")
    with pytest.raises(SystemExit):
        seed.main()


def test_no_demo_with_admin_credentials_creates_only_the_admin(client, monkeypatch):
    _empty_db_with(monkeypatch, demo=False, email="Boss@Clinic.uz", password="long-enough-pass")
    seed.main()
    res = client.post("/auth/login", json={"email": "boss@clinic.uz", "password": "long-enough-pass"})
    assert res.status_code == 200 and res.json()["user"]["role"] == "admin"
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get("/patients", headers=headers).json() == []  # demo ma'lumot yo'q
    assert client.post("/auth/login", json={"email": "admin@clinic.uz", "password": "password123"}).status_code == 401


def test_demo_seeds_only_empty_database(client, monkeypatch):
    _empty_db_with(monkeypatch, demo=True)
    seed.main()
    first = client.post("/auth/login", json={"email": "admin@clinic.uz", "password": "password123"})
    assert first.status_code == 200
    seed.main()  # ikkinchi marta: dublikat yo'q
    headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    assert len(client.get("/users", headers=headers).json()) == 7


def test_restart_with_existing_users_does_not_need_admin_password(monkeypatch):
    # bazada foydalanuvchilar bor (demo yuklangan), SEED_DEMO=false: ishga tushaveradi
    monkeypatch.setattr(settings, "seed_demo", False)
    monkeypatch.setattr(settings, "admin_password", "")
    seed.main()
