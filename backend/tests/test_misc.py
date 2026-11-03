import httpx

from app.core.config import settings
from app.services import llm


def test_ai_demo_mode_makes_no_external_calls(client, auth, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("tashqi so'rov yuborilmasligi kerak")

    monkeypatch.setattr(llm.httpx, "post", boom)
    res = client.post("/ai/chat", json={"message": "qon bosimi nima?"}, headers=auth("doctor"))
    assert res.status_code == 200
    body = res.json()
    assert body["demo"] is True and body["disclaimer"]
    assert client.post("/ai/analyze", json={"period": "month", "stats": "x"}, headers=auth("admin")).json()["demo"]
    assert client.get("/ai/status", headers=auth("admin")).json() == {"enabled": False, "demo": True}


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code, self._payload, self.text = status_code, payload or {}, "err"

    def json(self):
        return self._payload


def _enable_ai(monkeypatch, key="test-key"):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "llm_api_key", key)


def test_ai_enabled_uses_llm_with_mock(client, auth, monkeypatch):
    _enable_ai(monkeypatch)
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"], messages=json["messages"])
        return _Resp(200, {"choices": [{"message": {"content": "Mock javob"}}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    res = client.post("/ai/chat", json={"message": "salom", "history": [{"role": "user", "content": "oldingi"}]},
                      headers=auth("doctor"))
    assert res.status_code == 200
    body = res.json()
    assert body["response"] == "Mock javob" and body["demo"] is False and body["disclaimer"]
    assert seen["url"].endswith("/chat/completions") and seen["auth"] == "Bearer test-key"
    assert seen["messages"][-1] == {"role": "user", "content": "salom"}


def test_ai_error_mapping(client, auth, monkeypatch):
    _enable_ai(monkeypatch)
    h = auth("doctor")

    def timeout(*a, **k):
        raise httpx.TimeoutException("t")

    monkeypatch.setattr(llm.httpx, "post", timeout)
    assert client.post("/ai/chat", json={"message": "x"}, headers=h).status_code == 504

    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(500))
    assert client.post("/ai/chat", json={"message": "x"}, headers=h).status_code == 502

    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(200, {"unexpected": 1}))
    assert client.post("/ai/chat", json={"message": "x"}, headers=h).status_code == 502

    monkeypatch.setattr(settings, "llm_api_key", "")
    assert client.post("/ai/chat", json={"message": "x"}, headers=h).status_code == 503


def test_report_csv_has_utf8_bom(client, auth):
    res = client.get("/reports/download/2", headers=auth("admin"))
    assert res.status_code == 200 and res.content.startswith(b"\xef\xbb\xbf")
    assert client.get("/reports/download/99", headers=auth("admin")).status_code == 404


def test_settings_roundtrip(client, auth):
    h = auth("admin")
    body = client.get("/settings", headers=h).json()
    body["clinic_name"] = "Yangi nom"
    assert client.put("/settings", json=body, headers=h).status_code == 200
    assert client.get("/settings", headers=h).json()["clinic_name"] == "Yangi nom"


def test_staff_update_and_delete_rules(client, auth):
    h = auth("admin")
    staff = client.get("/staff", headers=h).json()
    nurse = next(s for s in staff if s["role"] == "Nurse")
    assert client.put(f"/staff/{nurse['id']}", json={"department": "Yangi"}, headers=h).json()["department"] == "Yangi"
    assert client.put("/staff/00000000-0000-0000-0000-000000000000", json={"name": "x"}, headers=h).status_code == 404
    doctor = next(s for s in staff if s["role"] == "Doctor")
    assert client.delete(f"/staff/{doctor['id']}", headers=h).status_code == 409  # yozuvlari bor


def test_cors_allows_only_configured_origin(client):
    ok = client.options("/patients", headers={"Origin": "http://localhost:5180", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5180"
    bad = client.options("/patients", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers
