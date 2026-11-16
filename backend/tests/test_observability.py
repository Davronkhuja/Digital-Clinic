"""Kuzatuv (v2.1.2): /health, /ready, tuzilmali JSON log PII'siz, so'rov ID, ixtiyoriy Sentry, /metrics (Celery navbati)."""
import json
import logging

import pytest

from app.core import logging_setup, observability
from app.core.config import settings
from app.db import session as db_session
from app.services import metrics


def test_health_and_ready(client, monkeypatch):
    assert client.get("/health").json() == {"status": "ok"}
    monkeypatch.setattr(metrics, "queue_length", lambda q="celery": 3)
    res = client.get("/ready")
    assert res.status_code == 200 and res.json() == {"status": "ok", "database": "ok", "redis": "ok"}
    monkeypatch.setattr(metrics, "queue_length", lambda q="celery": None)
    assert client.get("/ready").json()["redis"] == "down" and client.get("/ready").status_code == 200       # Redis yo'q: API ishlayveradi


def test_ready_is_503_when_database_is_down(client):
    from app.main import app

    class Broken:
        def execute(self, *a, **k):
            raise RuntimeError("db down")

    app.dependency_overrides[db_session.get_db] = lambda: Broken()
    try:
        res = client.get("/ready")
    finally:
        app.dependency_overrides.pop(db_session.get_db, None)
    assert res.status_code == 503 and res.json()["database"] == "down"
    assert client.get("/health").status_code == 200                                                         # jarayon tirik


def test_access_log_has_route_template_and_no_pii(client, auth, caplog):
    logging.getLogger("app.access").disabled = False          # conftest'dagi alembic fileConfig mavjud loggerlarni o'chirib qo'yadi (productionda bunday emas)
    caplog.set_level(logging.INFO, logger="app.access")
    res = client.get("/patients", params={"search": "+998901234567", "phone": "ali@example.com"}, headers={**auth("admin"), "X-Request-ID": "req-abc-123"})
    assert res.status_code == 200 and res.headers["X-Request-ID"] == "req-abc-123"
    rec = next(r for r in caplog.records if r.name == "app.access" and r.route == "/patients")
    assert (rec.method, rec.status, rec.request_id) == ("GET", 200, "req-abc-123") and rec.duration_ms >= 0
    dump = json.dumps({k: str(v) for k, v in rec.__dict__.items()})
    assert "998901234567" not in dump and "ali@example.com" not in dump and "search" not in dump
    # yo'l parametrli marshrut: shablon yoziladi, ID emas
    pid = client.get("/patients", headers=auth("admin")).json()[0]["id"]
    caplog.clear()
    client.get(f"/patients/{pid}", headers=auth("admin"))
    rec = next(r for r in caplog.records if r.name == "app.access" and r.route.startswith("/patients"))
    assert rec.route == "/patients/{patient_id}" and pid not in json.dumps({k: str(v) for k, v in rec.__dict__.items()})
    # tirikligi tekshiruvi jurnalni to'ldirmaydi
    caplog.clear()
    client.get("/health")
    assert not [r for r in caplog.records if r.name == "app.access"]


def test_json_formatter_and_pii_redaction():
    rec = logging.LogRecord("x", logging.WARNING, __file__, 1, "Bemor %s, tel +998 90 123 45 67, pinfl 12345678901234, mail ali@mail.uz, jwt eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0NTY.abcdefgh",
                            ("Ali",), None)
    rec.request_id = "r1"
    assert logging_setup.PiiFilter().filter(rec)
    out = json.loads(logging_setup.JsonFormatter().format(rec))
    assert out["level"] == "WARNING" and out["request_id"] == "r1" and out["ts"].endswith("+00:00")
    for secret in ("998 90 123", "12345678901234", "ali@mail.uz", "eyJhbGci"):
        assert secret not in out["msg"]
    assert "Bemor Ali" in out["msg"] and "[number]" in out["msg"] and "[email]" in out["msg"] and "[token]" in out["msg"]
    try:
        raise ValueError("xato: ali@mail.uz")
    except ValueError:
        import sys
        rec2 = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", (), sys.exc_info())
    assert "ali@mail.uz" not in json.loads(logging_setup.JsonFormatter().format(rec2))["exc"]


def test_json_logs_default_to_production(monkeypatch):
    monkeypatch.setattr(settings, "log_format", "")
    monkeypatch.setattr(settings, "app_env", "production")
    assert settings.json_logs
    monkeypatch.setattr(settings, "app_env", "development")
    assert not settings.json_logs
    monkeypatch.setattr(settings, "log_format", "json")
    assert settings.json_logs


def test_sentry_is_optional_and_sends_no_pii(monkeypatch):
    assert observability.init_sentry() is False                                                              # DSN yo'q: hech narsa
    import sentry_sdk
    seen = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: seen.update(kw))
    monkeypatch.setattr(settings, "sentry_dsn", "https://key@sentry.example.org/1")
    assert observability.init_sentry() is True
    assert seen["send_default_pii"] is False and seen["max_request_body_size"] == "never"
    ev = observability._scrub({"request": {"data": {"phone": "+998"}, "headers": {"authorization": "x"}, "url": "/p"}, "user": {"email": "a@b.c"}}, {})
    assert ev == {"request": {"url": "/p"}}


def test_metrics_endpoint_needs_token_and_reports_queue(client, auth, monkeypatch):
    assert client.get("/metrics").status_code == 404                                                         # token yo'q: o'chiq
    monkeypatch.setattr(settings, "metrics_token", "m" * 40)
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers=auth("admin")).status_code == 401                                   # xodim tokeni mos emas
    monkeypatch.setattr(metrics, "queue_length", lambda q="celery": 7)
    body = client.get("/metrics", headers={"Authorization": f"Bearer {'m' * 40}"})
    assert body.status_code == 200 and body.headers["content-type"].startswith("text/plain")
    assert 'clinic_celery_queue_length{queue="celery"} 7' in body.text and "clinic_redis_up 1" in body.text
    assert 'clinic_messages_total{status="Queued"}' in body.text and "clinic_messages_overdue_queued" in body.text
    monkeypatch.setattr(metrics, "queue_length", lambda q="celery": None)
    down = client.get("/metrics", headers={"Authorization": f"Bearer {'m' * 40}"}).text
    assert "clinic_redis_up 0" in down and "clinic_celery_queue_length" not in down.replace("# HELP clinic_celery_queue_length", "").replace("# TYPE clinic_celery_queue_length", "")


@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_ops_endpoints_need_no_auth(client, path):
    assert client.get(path).status_code == 200
