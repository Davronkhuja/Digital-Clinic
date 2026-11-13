"""Tasdiqlangan lab natijasi: tahrirlanmaydi, tuzatish yozuvi (kim, qachon, sabab), audit."""
import uuid

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.test_portal import _completed_order, _patient


def test_correction_record_who_when_why_and_audit(client, auth):
    pid = _patient(client, auth, "Tuzatish Bemor")
    oid = _completed_order(client, auth, pid)
    doctor = auth("doctor")
    item = client.get(f"/lab/orders/{oid}", headers=doctor).json()["items"][0]
    body = {"reason": "Analizator xatosi", "results": [{"item_id": item["id"], "value": 5.2}]}
    assert client.post(f"/lab/orders/{oid}/corrections", headers=doctor, json=body).status_code == 409      # tasdiqlanmagan
    assert client.post(f"/lab/orders/{oid}/approve", headers=auth("nurse")).status_code == 403
    approved = client.post(f"/lab/orders/{oid}/approve", headers=doctor).json()
    assert approved["approved_by"] == "Dr. Behruz Rustamov" and approved["corrections"] == []
    assert client.post(f"/lab/orders/{oid}/corrections", headers=auth("nurse"), json=body).status_code == 403
    assert client.post(f"/lab/orders/{oid}/corrections", headers=doctor, json={**body, "reason": "xato"}).status_code == 422   # sabab qisqa
    assert client.post(f"/lab/orders/{oid}/corrections", headers=doctor,
                       json={**body, "results": [{"item_id": item["id"], "value": item["value"]}]}).status_code == 422      # o'zgarmadi
    out = client.post(f"/lab/orders/{oid}/corrections", headers=doctor, json=body).json()
    assert out["approved"] is True and out["items"][0]["value"] == 5.2 and out["items"][0]["flag"] == "Normal"
    c = out["corrections"][0]
    assert (c["old_value"], c["new_value"], c["old_flag"], c["new_flag"]) == (6.5, 5.2, "High", "Normal")
    assert c["reason"] == "Analizator xatosi" and c["corrected_by"] == "Dr. Behruz Rustamov" and c["corrected_at"]
    assert client.get(f"/lab/orders/{oid}", headers=doctor).json()["corrections"][0]["id"] == c["id"]
    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "lab_order", AuditLog.entity_id == uuid.UUID(oid))).all()
        assert any("correction" in (r.details or {}) and r.details["reason"] == "Analizator xatosi" for r in rows)
