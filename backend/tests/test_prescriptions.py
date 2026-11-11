import csv

from app.db.session import SessionLocal
from app.services.inn import STARTER_CSV, import_csv
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"
RX = {"inn": "Amlodipine", "dose": "5 mg", "route": "Oral", "frequency": "kuniga 1 marta", "duration_days": 30}


def _encounter(client, auth):
    pid = client.post("/patients", json=NEW, headers=auth("admin")).json()["id"]
    return client.post("/emr", headers=auth("doctor"), json={
        "patient_id": pid, "doctor": DOC, "diagnosis": "Gipertenziya", "icd_code": "I10", "prescription": "-",
        "visit_date": "2026-12-01"}).json()


def test_starter_csv_and_search(client, auth):
    with open(STARTER_CSV, encoding="utf-8-sig") as fh:
        names = [r["inn"].lower() for r in csv.DictReader(fh)]
    assert len(names) == len(set(names)) >= 100
    h = auth("doctor")
    assert client.get("/inn", params={"search": "amlo"}, headers=h).json()[0]["inn"] == "amlodipine"
    assert any(d["inn"] == "amoxicillin and clavulanic acid" for d in client.get("/inn", params={"search": "clavul"}, headers=h).json())
    assert any(d["inn"] == "atorvastatin" for d in client.get("/inn", params={"search": "statin"}, headers=h).json())
    assert client.get("/inn", headers=auth("cashier")).status_code == 403


def test_inn_import_idempotent(tmp_path):
    path = tmp_path / "inn.csv"
    path.write_text("inn,group_uz\nTestdrug,Guruh\nparacetamol,Yangi guruh\n,Bo'sh\n", encoding="utf-8")
    with SessionLocal() as db:
        assert import_csv(db, path) == {"created": 1, "updated": 1, "skipped": 1}
        db.commit()
        assert import_csv(db, path) == {"created": 0, "updated": 2, "skipped": 1}


def test_structured_prescription_flow(client, auth):
    enc = _encounter(client, auth)
    doc = auth("doctor")
    res = client.post(f"/emr/{enc['id']}/prescriptions", headers=doc, json={**RX, "instructions": "Ovqatdan keyin"})
    assert res.status_code == 201
    rx = res.json()
    assert rx["inn"] == "amlodipine"                                    # kanonik nom
    assert rx["medication"] == "amlodipine 5 mg, ichga, kuniga 1 marta, 30 kun"
    assert (rx["dose"], rx["route"], rx["duration_days"]) == ("5 mg", "Oral", 30)
    client.post(f"/emr/{enc['id']}/prescriptions", headers=doc, json={**RX, "inn": "METFORMIN", "dose": "500 mg",
                                                                      "frequency": "kuniga 2 marta", "duration_days": 90})
    record = client.get(f"/emr/{enc['id']}", headers=doc).json()
    assert [p["inn"] for p in record["prescriptions"]] == ["amlodipine", "metformin"]
    assert "amlodipine 5 mg" in record["prescription"] and "metformin 500 mg" in record["prescription"]   # yig'ma matn
    assert [p["id"] for p in client.get(f"/emr/{enc['id']}/prescriptions", headers=doc).json()] == [p["id"] for p in record["prescriptions"]]


def test_prescription_validation_and_permissions(client, auth):
    enc = _encounter(client, auth)
    doc = auth("doctor")
    url = f"/emr/{enc['id']}/prescriptions"
    assert client.post(url, headers=doc, json={**RX, "inn": "noma'lum dori"}).status_code == 422   # ro'yxatda yo'q
    for bad in ({"duration_days": 0}, {"duration_days": 366}, {"route": "Yo'q"}, {"dose": ""}, {"frequency": ""}):
        assert client.post(url, headers=doc, json={**RX, **bad}).status_code == 422, bad
    assert client.post(url, headers=auth("nurse"), json=RX).status_code == 403                    # emr:write yo'q
    assert client.get(url, headers=auth("nurse")).status_code == 200
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/emr/{missing}/prescriptions", headers=doc, json=RX).status_code == 404


def test_prescription_never_deleted_only_cancelled_and_audited(client, auth):
    enc = _encounter(client, auth)
    doc = auth("doctor")
    rx = client.post(f"/emr/{enc['id']}/prescriptions", headers=doc, json=RX).json()
    assert client.delete(f"/prescriptions/{rx['id']}", headers=doc).status_code == 200
    assert client.delete(f"/prescriptions/{rx['id']}", headers=doc).status_code == 404            # allaqachon bekor
    assert client.get(f"/emr/{enc['id']}/prescriptions", headers=doc).json() == []
    from sqlalchemy import text
    with SessionLocal() as db:                                                                   # qator bazada qoladi
        row = db.execute(text("select deleted_at is not null from prescriptions where id = :i"), {"i": rx["id"]}).one()
        assert row[0] is True
    audit = client.get("/security/audit", params={"entity_type": "prescription", "limit": 20}, headers=auth("admin")).json()["items"]
    assert {e["action"] for e in audit} >= {"create", "delete"}


def test_add_inn_admin_only(client, auth):
    assert client.post("/inn", headers=auth("doctor"), json={"inn": "newdrug"}).status_code == 403
    assert client.post("/inn", headers=auth("admin"), json={"inn": "newdrug", "group_uz": "Yangi"}).status_code == 201
    assert client.post("/inn", headers=auth("admin"), json={"inn": "NewDrug"}).status_code == 409
    enc = _encounter(client, auth)
    assert client.post(f"/emr/{enc['id']}/prescriptions", headers=auth("doctor"), json={**RX, "inn": "newdrug"}).status_code == 201
