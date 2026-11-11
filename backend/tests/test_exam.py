from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def _patient(client, h, name="Ko'rik Sinov"):
    return client.post("/patients", json={**NEW, "name": name}, headers=h).json()["id"]


def _appt(client, h, pid, **kw):
    return client.post("/appointments", headers=h, json={
        "patient_id": pid, "doctor": DOC, "date": "2026-12-01", "time": "10:00", "type": "Konsultatsiya", **kw})


def test_structured_sections_roundtrip_and_edit_is_audited(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    pid = _patient(client, admin)
    res = client.post("/emr", headers=doc, json={
        "patient_id": pid, "doctor": DOC, "diagnosis": "Gipertenziya", "icd_code": "I10", "prescription": "-",
        "visit_date": "2026-12-01", "complaints": "Bosh og'rig'i", "anamnesis": "3 yildan beri",
        "examination": "AQB 150/95", "recommendations": "Tuzni kamaytirish"})
    assert res.status_code == 201
    rec = res.json()
    assert (rec["complaints"], rec["anamnesis"], rec["examination"], rec["recommendations"]) == (
        "Bosh og'rig'i", "3 yildan beri", "AQB 150/95", "Tuzni kamaytirish")
    upd = client.put(f"/emr/{rec['id']}", headers=doc, json={"examination": "AQB 130/85", "icd_code": "e11"})
    assert upd.status_code == 200 and upd.json()["examination"] == "AQB 130/85" and upd.json()["icd_code"] == "E11"
    assert upd.json()["complaints"] == "Bosh og'rig'i"                       # yuborilmagan maydon o'zgarmadi
    assert client.put(f"/emr/{rec['id']}", headers=doc, json={"icd_code": "Q99"}).status_code == 422
    assert client.put(f"/emr/{rec['id']}", headers=auth("nurse"), json={"notes": "x"}).status_code == 403
    audit = client.get("/security/audit", params={"entity_type": "emr", "limit": 50}, headers=admin).json()["items"]
    assert any(e["action"] == "update" and e["entity_id"] == rec["id"] for e in audit)


def test_encounter_completes_linked_appointment(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    pid = _patient(client, admin)
    appt = _appt(client, admin, pid).json()
    rec = client.post("/emr", headers=doc, json={"patient_id": pid, "doctor": DOC, "diagnosis": "Test", "prescription": "-",
                                                  "visit_date": "2026-12-01", "appointment_id": appt["id"]})
    assert rec.status_code == 201 and rec.json()["appointment_id"] == appt["id"]
    after = client.get("/appointments", params={"patient_id": pid}, headers=admin).json()[0]
    assert after["status"] == "Completed"
    # boshqa bemorning qabuli yoki bekor qilingani
    other = _patient(client, admin, "Boshqa Bemor")
    assert client.post("/emr", headers=doc, json={"patient_id": other, "doctor": DOC, "diagnosis": "x", "prescription": "-",
                                                  "visit_date": "2026-12-01", "appointment_id": appt["id"]}).status_code == 422
    appt2 = _appt(client, admin, pid, time="11:00").json()
    client.patch(f"/appointments/{appt2['id']}/status", params={"status": "Cancelled"}, headers=admin)
    assert client.post("/emr", headers=doc, json={"patient_id": pid, "doctor": DOC, "diagnosis": "x", "prescription": "-",
                                                  "visit_date": "2026-12-01", "appointment_id": appt2["id"]}).status_code == 409


def test_templates_crud(client, auth):
    doc = auth("doctor")
    seeded = client.get("/emr-templates", headers=auth("nurse")).json()
    assert {t["name"] for t in seeded} >= {"Umumiy ko'rik (andoza)", "Qayta ko'rik (andoza)"}
    new = client.post("/emr-templates", headers=doc, json={"name": "Kardiolog", "specialty": "Kardiologiya",
                                                            "complaints": "Ko'krak og'rig'i:"})
    assert new.status_code == 201
    assert client.post("/emr-templates", headers=doc, json={"name": "kardiolog"}).status_code == 409
    assert client.post("/emr-templates", headers=auth("nurse"), json={"name": "Hamshira"}).status_code == 403
    tid = new.json()["id"]
    assert client.put(f"/emr-templates/{tid}", headers=doc, json={"examination": "AQB:"}).json()["examination"] == "AQB:"
    assert client.put(f"/emr-templates/{tid}", headers=doc, json={"is_active": False}).status_code == 200
    assert "Kardiolog" not in [t["name"] for t in client.get("/emr-templates", headers=doc).json()]
    assert "Kardiolog" in [t["name"] for t in client.get("/emr-templates", params={"include_inactive": True}, headers=doc).json()]
    assert client.delete(f"/emr-templates/{tid}", headers=doc).status_code == 200
    assert client.delete(f"/emr-templates/{tid}", headers=doc).status_code == 404
