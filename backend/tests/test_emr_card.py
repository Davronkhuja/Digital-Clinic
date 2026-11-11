import io

from pypdf import PdfReader

from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def _full_encounter(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    pid = client.post("/patients", json={**NEW, "name": "Karta Bemor", "gender": "female", "birth_date": "1985-06-15", "age": None,
                                         "pinfl": "31506850000019", "address": "Toshkent, Yunusobod"}, headers=admin).json()["id"]
    enc = client.post("/emr", headers=doc, json={
        "patient_id": pid, "doctor": DOC, "diagnosis": "Gipertenziya 2-daraja", "icd_code": "I10", "prescription": "-",
        "visit_date": "2026-12-01", "complaints": "Bosh og'rig'i", "anamnesis": "3 yildan beri", "examination": "AQB 150/95",
        "recommendations": "Tuz kamaytirish"}).json()
    client.post(f"/emr/{enc['id']}/prescriptions", headers=doc, json={
        "inn": "amlodipine", "dose": "5 mg", "route": "Oral", "frequency": "kuniga 1 marta", "duration_days": 30,
        "instructions": "Ovqatdan keyin"})
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=doc).json()}
    order = client.post("/lab/orders", headers=doc, json={"patient_id": pid, "doctor": DOC, "encounter_id": enc["id"],
                                                         "test_ids": [tests["GLU"]["id"], tests["HGB"]["id"]]}).json()
    client.put(f"/lab/orders/{order['id']}/results", headers=doc, json={
        "results": [{"item_id": order["items"][0]["id"], "value": 7.1}]})                       # HGB tartibida birinchi
    return pid, enc


def test_card_fields_in_dmed_order_with_icd_rx_and_lab(client, auth):
    _, enc = _full_encounter(client, auth)
    card = client.get(f"/emr/{enc['id']}/card", headers=auth("doctor")).json()
    assert [f["key"] for f in card["patient"]] == ["full_name", "birth_date", "gender", "pinfl", "phone", "address"]
    assert [f["key"] for f in card["visit"]] == ["visit_date", "doctor"]
    assert [f["key"] for f in card["sections"]] == ["complaints", "anamnesis", "examination", "diagnosis", "recommendations"]
    values = {f["key"]: f["value"] for f in card["patient"] + card["visit"] + card["sections"]}
    assert values["full_name"] == "Karta Bemor" and values["gender"] == "Ayol" and values["pinfl"] == "31506850000019"
    assert values["complaints"] == "Bosh og'rig'i" and values["doctor"] == DOC and values["visit_date"] == "2026-12-01"
    assert card["icd_code"] == "I10" and "gipertenziya" in card["icd_name"].lower()
    rx = card["prescriptions"][0]
    assert (rx["inn"], rx["dose"], rx["route"], rx["duration_days"]) == ("amlodipine", "5 mg", "ichga", 30)
    assert rx["text"] == "amlodipine 5 mg, ichga, kuniga 1 marta, 30 kun"
    assert len(card["lab_results"]) == 1 and card["lab_results"][0]["flag"] == "High"          # faqat natijasi borlari
    assert card["dmed_copied_at"] is None


def test_empty_sections_are_null_and_card_requires_emr_read(client, auth):
    pid = client.post("/patients", json=NEW, headers=auth("admin")).json()["id"]
    enc = client.post("/emr", headers=auth("doctor"), json={"patient_id": pid, "doctor": DOC, "diagnosis": "x", "prescription": "-",
                                                             "visit_date": "2026-12-01"}).json()
    card = client.get(f"/emr/{enc['id']}/card", headers=auth("nurse")).json()
    assert {f["key"]: f["value"] for f in card["sections"]}["complaints"] is None and card["icd_name"] is None
    assert client.get(f"/emr/{enc['id']}/card", headers=auth("cashier")).status_code == 403
    assert client.get("/emr/00000000-0000-0000-0000-000000000000/card", headers=auth("doctor")).status_code == 404


def test_dmed_mark_manual_toggle_and_audit(client, auth):
    _, enc = _full_encounter(client, auth)
    doc = auth("doctor")
    assert client.post(f"/emr/{enc['id']}/dmed-mark", headers=auth("nurse"), json={"copied": True}).status_code == 403
    marked = client.post(f"/emr/{enc['id']}/dmed-mark", headers=doc, json={"copied": True}).json()
    assert marked["dmed_copied_at"] and marked["dmed_copied_by"] == DOC
    assert client.get(f"/emr/{enc['id']}", headers=doc).json()["dmed_copied_at"]
    cleared = client.post(f"/emr/{enc['id']}/dmed-mark", headers=doc, json={"copied": False}).json()
    assert cleared["dmed_copied_at"] is None and cleared["dmed_copied_by"] is None
    audit = client.get("/security/audit", params={"entity_type": "emr", "limit": 100}, headers=auth("admin")).json()["items"]
    assert [e for e in audit if e["action"] == "update" and (e.get("details") or {}).get("dmed_copied") is True]


def test_card_pdf(client, auth):
    _, enc = _full_encounter(client, auth)
    res = client.get(f"/emr/{enc['id']}/card/pdf", headers=auth("doctor"))
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(res.content)).pages)
    for needle in ("Karta Bemor", "31506850000019", "Bosh og'rig'i", "I10", "amlodipine", "ichga", "Glyukoza", "DMED ga ko'chirilmagan"):
        assert needle in text, needle
    client.post(f"/emr/{enc['id']}/dmed-mark", headers=auth("doctor"), json={"copied": True})
    again = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(client.get(f"/emr/{enc['id']}/card/pdf", headers=auth("doctor")).content)).pages)
    assert "DMED ga ko'chirildi:" in again


def test_lab_order_encounter_must_match_patient(client, auth):
    pid, enc = _full_encounter(client, auth)
    other = client.post("/patients", json={**NEW, "name": "Boshqa Bemor"}, headers=auth("admin")).json()["id"]
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=auth("doctor")).json()}
    res = client.post("/lab/orders", headers=auth("doctor"), json={"patient_id": other, "doctor": DOC, "encounter_id": enc["id"],
                                                                  "test_ids": [tests["GLU"]["id"]]})
    assert res.status_code == 422 and pid
