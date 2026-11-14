"""Ko'rik xulosasi AI (v1.9.29): lokal LLM, shaxsiy ma'lumotsiz so'rov, qoralama shifokor tasdiqlamaguncha yozuvga kirmaydi."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AuditLog, EncounterSummary
from app.services import ai_summary, llm
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


class _Resp:
    def __init__(self, content="Bemor bosh og'riqqa shikoyat qildi. Tashxis: gipertoniya. Davo buyurildi.", status=200):
        self.status_code, self._p, self.text = status, {"choices": [{"message": {"content": content}}]}, "err"

    def json(self):
        return self._p


@pytest.fixture
def enc(client, auth):
    admin = auth("admin")
    pid = client.post("/patients", json={**NEW, "name": "Maxfiy Ismli Bemor", "phone": "+998 90 999 88 77", "address": "Yashirin ko'cha 5"}, headers=admin).json()["id"]
    res = client.post("/emr", headers=auth("doctor"), json={"patient_id": pid, "doctor": DOC, "diagnosis": "Gipertoniya", "complaints": "Bosh og'rig'i", "anamnesis": "5 yildan beri",
                                                            "examination": "AB 160/100", "recommendations": "Tuz kamaytirish", "prescription": "Amlodipin 5 mg kuniga 1 marta", "visit_date": date.today().isoformat()})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _enable(monkeypatch, base="http://llm-gpu:8000/v1"):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "llm_base_url", base)
    monkeypatch.setattr(settings, "llm_require_key", False)
    monkeypatch.setattr(settings, "llm_api_key", "")


def test_local_llm_draft_does_not_reach_record_until_doctor_approves(client, auth, enc, monkeypatch):
    _enable(monkeypatch)
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, messages=json["messages"])
        return _Resp()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    doctor = auth("doctor")
    empty = client.get(f"/emr/{enc}/ai-summary", headers=doctor).json()
    assert (empty["ai_enabled"], empty["draft"], empty["approved"], empty["can_review"]) == (True, None, None, True) and empty["disclaimer"]
    res = client.post(f"/emr/{enc}/ai-summary", headers=doctor)
    assert res.status_code == 201, res.text
    draft = res.json()["draft"]
    assert draft["status"] == "Draft" and draft["source"] == "llm" and draft["demo"] is False and draft["model"] == settings.llm_model and res.json()["approved"] is None
    assert seen["url"] == "http://llm-gpu:8000/v1/chat/completions" and "Authorization" not in seen["headers"]                  # lokal LLM: kalitsiz
    prompt = " ".join(m["content"] for m in seen["messages"])
    assert "Gipertoniya" in prompt and "Bosh og'rig'i" in prompt and "AB 160/100" in prompt
    for secret in ("Maxfiy", "Ismli", "+998", "998909998877", "Yashirin"):
        assert secret not in prompt                                                                                       # shaxsiy ma'lumot yuborilmaydi
    assert "yoshi" in prompt
    # qoralama tibbiy yozuvga kirmagan
    assert client.get(f"/emr/{enc}", headers=doctor).json()["diagnosis"] == "Gipertoniya" and "ai_summary" not in client.get(f"/emr/{enc}", headers=doctor).json()
    assert client.get(f"/emr/{enc}/ai-summary", headers=doctor).json()["approved"] is None
    assert res.json()["can_review"] is True and client.get(f"/emr/{enc}/ai-summary", headers=auth("admin")).json()["can_review"] is False           # admin ko'rik shifokori emas
    assert client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=auth("admin")).status_code == 403
    assert client.post(f"/emr/{enc}/ai-summary/{draft['id']}/reject", headers=auth("admin")).status_code == 403
    # tasdiqlash: faqat ko'rik shifokori; tahrir belgisi
    nurse = auth("nurse")
    assert client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=nurse).status_code == 403                    # emr:write yo'q
    short = client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=doctor, json={"text": "qisqa"})
    assert short.status_code == 422
    ok = client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=doctor, json={"text": draft["text"] + " Qo'shimcha: 2 haftadan keyin qayta ko'rik."})
    assert ok.status_code == 200, ok.text
    approved = ok.json()["approved"]
    assert approved["status"] == "Approved" and approved["edited"] is True and approved["text"].endswith("qayta ko'rik.") and approved["original_text"] == draft["text"]
    assert ok.json()["draft"] is None and approved["reviewed_by"]
    assert client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=doctor).status_code == 409                    # ikki marta emas
    # yangi qoralama + tasdiq: eskisi almashtiriladi
    d2 = client.post(f"/emr/{enc}/ai-summary", headers=doctor).json()["draft"]
    again = client.post(f"/emr/{enc}/ai-summary/{d2['id']}/approve", headers=doctor).json()
    assert again["approved"]["id"] == d2["id"] and again["approved"]["edited"] is False
    with SessionLocal() as db:
        statuses = [r.status for r in db.scalars(select(EncounterSummary).order_by(EncounterSummary.created_at))]
        assert statuses == ["Superseded", "Approved"]
        acts = {(r.action, r.details.get("status") or r.details.get("source")) for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "ai_summary"))}
        assert ("create", "llm") in acts and ("update", "Approved") in acts and any(a[0] == "read" for a in acts)


def test_reject_regenerate_demo_and_external_llm_rules(client, auth, enc, monkeypatch):
    doctor = auth("doctor")
    # AI o'chiq: statik demo, tasdiqlanmaydi
    res = client.post(f"/emr/{enc}/ai-summary", headers=doctor)
    assert res.status_code == 201 and res.json()["ai_enabled"] is False and res.json()["draft"]["demo"] is True and res.json()["draft"]["text"].startswith("[Demo rejim")
    demo = res.json()["draft"]
    assert client.post(f"/emr/{enc}/ai-summary/{demo['id']}/approve", headers=doctor).status_code == 409
    # AI yoqilgan: tashqi (lokal bo'lmagan) LLM bemor ma'lumotini olmaydi
    _enable(monkeypatch, "https://api.groq.com/openai/v1")
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp())
    blocked = client.post(f"/emr/{enc}/ai-summary", headers=doctor)
    assert blocked.status_code == 409 and "lokal LLM" in blocked.json()["detail"]
    monkeypatch.setattr(settings, "llm_allow_external_phi", True)                                                          # ongli qaror bilan ruxsat
    allowed = client.post(f"/emr/{enc}/ai-summary", headers=doctor)
    assert allowed.status_code == 201 and allowed.json()["draft"]["source"] == "llm"
    first = allowed.json()["draft"]
    second = client.post(f"/emr/{enc}/ai-summary", headers=doctor).json()["draft"]                                         # yangisi eskisini rad etadi
    assert second["id"] != first["id"]
    with SessionLocal() as db:
        assert [r.status for r in db.scalars(select(EncounterSummary).order_by(EncounterSummary.created_at))] == ["Rejected", "Rejected", "Draft"]
    rej = client.post(f"/emr/{enc}/ai-summary/{second['id']}/reject", headers=doctor)
    assert rej.status_code == 200 and rej.json()["draft"] is None and rej.json()["approved"] is None
    assert client.post(f"/emr/{enc}/ai-summary/{second['id']}/reject", headers=doctor).status_code == 409
    assert client.post(f"/emr/{enc}/ai-summary/00000000-0000-0000-0000-000000000000/approve", headers=doctor).status_code == 404
    assert client.get("/emr/00000000-0000-0000-0000-000000000000/ai-summary", headers=doctor).status_code == 404
    assert client.post(f"/emr/{enc}/ai-summary", headers=auth("cashier")).status_code == 403                                 # ai:use yo'q


def test_llm_errors_and_helpers(client, auth, enc, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(content="   "))
    assert client.post(f"/emr/{enc}/ai-summary", headers=auth("doctor")).status_code == 502                                  # bo'sh javob
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(status=500))
    assert client.post(f"/emr/{enc}/ai-summary", headers=auth("doctor")).status_code == 502
    with SessionLocal() as db:
        assert db.scalars(select(EncounterSummary)).all() == []                                                            # xatoda qoralama yozilmaydi
    for url, local in (("http://localhost:8000/v1", True), ("http://127.0.0.1:11434/v1", True), ("http://192.168.0.2:8000/v1", True), ("http://10.1.2.3/v1", True),
                       ("http://llm-gpu:8000/v1", True), ("http://vllm.internal/v1", True), ("https://api.groq.com/openai/v1", False), ("https://8.8.8.8/v1", False), ("not a url", False)):
        assert ai_summary.is_local_llm(url) is local, url
    monkeypatch.setattr(settings, "llm_require_key", True)
    monkeypatch.setattr(settings, "llm_api_key", "")
    assert client.post(f"/emr/{enc}/ai-summary", headers=auth("doctor")).status_code == 503                                  # kalit talab qilinsa va yo'q bo'lsa
