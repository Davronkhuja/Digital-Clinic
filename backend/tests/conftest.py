"""Test muhiti: alohida PostgreSQL bazasi (`<nom>_test`), Alembic migratsiyalari bilan yaratiladi.

Har bir test oldidan jadvallar tozalanadi va boshlang'ich + demo ma'lumotlar yuklanadi.
"""
import os
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent

_base_url = make_url(os.environ["DATABASE_URL"])
_test_url = _base_url.set(database=f"{_base_url.database}_test")
os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)
os.environ.setdefault("JWT_SECRET", "t" * 48)
os.environ["AI_ENABLED"] = "false"
os.environ["SEED_DEMO"] = "true"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["LLM_API_KEY"] = ""

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo, seed_essentials  # noqa: E402

DEMO_USERS = {
    "admin": "admin@clinic.uz",
    "doctor": "rustamov@clinic.uz",
    "nurse": "yusupova@clinic.uz",
    "receptionist": "mirzayev@clinic.uz",
    "cashier": "akbarova@clinic.uz",
}
PASSWORD = "password123"


@pytest.fixture(scope="session", autouse=True)
def _database():
    admin_dsn = _base_url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{_test_url.database}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{_test_url.database}"')
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


def truncate_all() -> None:
    with SessionLocal() as db:
        tables = db.execute(
            text("select tablename from pg_tables where schemaname='public' and tablename <> 'alembic_version'")
        ).scalars().all()
        db.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
        db.commit()


def reset_data() -> None:
    truncate_all()
    with SessionLocal() as db:
        branch = seed_essentials(db)
        seed_demo(db, branch)
        db.commit()


@pytest.fixture(autouse=True)
def _fresh_data(_database):
    reset_data()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def login(client: TestClient, role: str = "admin", email: str | None = None, password: str = PASSWORD) -> dict:
    res = client.post("/auth/login", json={"email": email or DEMO_USERS[role], "password": password})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.fixture
def auth(client):
    """auth('doctor') -> Authorization header."""

    def make(role: str = "admin") -> dict:
        return {"Authorization": f"Bearer {login(client, role)['access_token']}"}

    return make
