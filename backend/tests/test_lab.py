from datetime import date, timedelta
from decimal import Decimal

from app.models import LabReferenceRange
from app.schemas.enums import GenderEnum, LabFlag
from app.services.lab import classify, pick_range
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def _r(sex=None, age_min=None, age_max=None, low=None, high=None):
    return LabReferenceRange(sex=sex, age_min=age_min, age_max=age_max, low=low, high=high)


def test_pick_range_prefers_sex_specific_then_narrow_age():
    generic = _r(None, 18, None, Decimal(1), Decimal(2))
    male = _r(GenderEnum.male, 18, None, Decimal(3), Decimal(4))
    child = _r(None, 0, 17, Decimal(5), Decimal(6))
    assert pick_range([generic, male, child], GenderEnum.male, 30) is male
    assert pick_range([generic, male, child], GenderEnum.female, 30) is generic
    assert pick_range([generic, male, child], GenderEnum.male, 10) is child
    assert pick_range([generic, male], GenderEnum.male, 10) is None            # bola uchun kattalar me'yori tanlanmaydi
    assert pick_range([generic], GenderEnum.male, None) is None                 # yosh noma'lum: yosh chegarali me'yor yo'q
    assert pick_range([_r(None, None, None, Decimal(1), Decimal(2))], GenderEnum.other, None) is not None
    assert pick_range([male], GenderEnum.other, 30) is None                     # jinsga xos me'yor 'other' ga mos emas


def test_classify_boundaries_and_one_sided():
    assert classify(Decimal("3.9"), Decimal("3.9"), Decimal("5.9")) == LabFlag.normal      # chegarada: me'yor
    assert classify(Decimal("5.91"), Decimal("3.9"), Decimal("5.9")) == LabFlag.high
    assert classify(Decimal("3.89"), Decimal("3.9"), Decimal("5.9")) == LabFlag.low
    assert classify(Decimal(100), None, Decimal(41)) == LabFlag.high
    assert classify(Decimal(0), None, Decimal(41)) == LabFlag.normal            # faqat yuqori chegara: past qiymat me'yor
    assert classify(Decimal(5), Decimal(1), None) == LabFlag.normal


def _setup(client, auth, gender="male", birth="1990-01-01", name="Lab Bemor"):
    pid = client.post("/patients", json={**NEW, "name": name, "gender": gender, "birth_date": birth, "age": None},
                      headers=auth("admin")).json()["id"]
    return pid


def _tests(client, auth):
    return {t["code"]: t for t in client.get("/lab/tests", headers=auth("doctor")).json()}


def _order(client, auth, pid, **kw):
    return client.post("/lab/orders", headers=auth("doctor"), json={"patient_id": pid, "doctor": DOC, **kw})


def test_starter_catalog_is_seeded(client, auth):
    tests = _tests(client, auth)
    assert len(tests) >= 24 and {"HGB", "GLU", "ALT", "CHOL"} <= set(tests)
    assert all(t["ranges"] and all(r["age_min"] == 18 for r in t["ranges"]) for t in tests.values())   # kattalar
    panels = {p["name"]: p["test_codes"] for p in client.get("/lab/panels", headers=auth("nurse")).json()}
    assert panels["Umumiy qon tahlili (UQT)"] == ["HGB", "RBC", "WBC", "PLT", "HCT", "ESR"]


def test_order_from_panel_enter_results_with_flags_by_sex(client, auth):
    tests = _tests(client, auth)
    man, woman = _setup(client, auth, "male", name="Erkak Bemor"), _setup(client, auth, "female", name="Ayol Bemor")
    panel = next(p for p in client.get("/lab/panels", headers=auth("doctor")).json() if p["name"].startswith("Umumiy qon"))
    out = {}
    for who, pid in (("m", man), ("f", woman)):
        res = _order(client, auth, pid, panel_ids=[panel["id"]], test_ids=[tests["HGB"]["id"]])   # HGB takror: bir marta
        assert res.status_code == 201
        order = res.json()
        assert order["status"] == "Ordered" and [i["code"] for i in order["items"]] == ["HGB", "RBC", "WBC", "PLT", "HCT", "ESR"]
        values = {"HGB": 125, "RBC": 4.5, "WBC": 12.0, "PLT": 100, "HCT": 45, "ESR": 5}
        results = [{"item_id": i["id"], "value": values[i["code"]]} for i in order["items"]]
        done = client.put(f"/lab/orders/{order['id']}/results", headers=auth("nurse"), json={"results": results}).json()
        out[who] = {i["code"]: i for i in done["items"]}
        assert done["status"] == "Completed" and done["completed_at"]
    # Hb 125: erkakda past (130-170), ayolda me'yor (120-150)
    assert out["m"]["HGB"]["flag"] == "Low" and out["m"]["HGB"]["reference"] == "130 - 170"
    assert out["f"]["HGB"]["flag"] == "Normal" and out["f"]["HGB"]["reference"] == "120 - 150"
    assert out["m"]["WBC"]["flag"] == "High" and out["m"]["PLT"]["flag"] == "Low" and out["m"]["ESR"]["flag"] == "Normal"
    assert out["m"]["HCT"]["flag"] == "Normal"                                        # 45: erkak 40-50
    assert out["f"]["HCT"]["flag"] == "Normal" and out["f"]["RBC"]["flag"] == "Normal"


def test_partial_results_then_complete_and_correction(client, auth):
    tests = _tests(client, auth)
    pid = _setup(client, auth)
    order = _order(client, auth, pid, test_ids=[tests["GLU"]["id"], tests["ALT"]["id"]]).json()
    glu, alt = order["items"]
    part = client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"),
                      json={"results": [{"item_id": next(i["id"] for i in order["items"] if i["code"] == "GLU"), "value": 7.2}]}).json()
    assert part["status"] == "Ordered" and {i["code"]: i["flag"] for i in part["items"]} == {"GLU": "High", "ALT": None}
    alt_id = next(i["id"] for i in part["items"] if i["code"] == "ALT")
    full = client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": [{"item_id": alt_id, "value": 30}]}).json()
    assert full["status"] == "Completed" and {i["code"]: i["flag"] for i in full["items"]} == {"GLU": "High", "ALT": "Normal"}
    fixed = client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": [{"item_id": alt_id, "value": 55}]}).json()
    assert next(i for i in fixed["items"] if i["code"] == "ALT")["flag"] == "High" and fixed["status"] == "Completed"
    assert glu and alt


def test_child_has_no_adult_reference(client, auth):
    tests = _tests(client, auth)
    child_birth = (date.today() - timedelta(days=365 * 8)).isoformat()
    pid = _setup(client, auth, "male", child_birth, "Bola Bemor")
    order = _order(client, auth, pid, test_ids=[tests["HGB"]["id"]]).json()
    done = client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"),
                      json={"results": [{"item_id": order["items"][0]["id"], "value": 110}]}).json()
    item = done["items"][0]
    assert item["flag"] is None and item["reference"] is None and item["value"] == 110.0


def test_results_snapshot_unchanged_when_catalog_edited(client, auth):
    admin = auth("admin")
    tests = _tests(client, auth)
    pid = _setup(client, auth)
    order = _order(client, auth, pid, test_ids=[tests["GLU"]["id"]]).json()
    client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": [{"item_id": order["items"][0]["id"], "value": 6.5}]})
    res = client.put(f"/lab/tests/{tests['GLU']['id']}", headers=admin,
                     json={"name": "Glyukoza (yangi nom)", "ranges": [{"low": 4.0, "high": 7.0}]})
    assert res.status_code == 200 and res.json()["ranges"][0]["high"] == 7.0
    again = client.get(f"/lab/orders/{order['id']}", headers=admin).json()["items"][0]
    assert again["name"] == "Glyukoza (och qoringa)" and again["flag"] == "High" and again["ref_high"] == 5.9   # eski me'yor/nom


def test_validation_permissions_cancel_and_audit(client, auth):
    tests = _tests(client, auth)
    pid = _setup(client, auth)
    assert _order(client, auth, pid).status_code == 422                                           # hech narsa tanlanmagan
    assert _order(client, auth, pid, test_ids=["00000000-0000-0000-0000-000000000000"]).status_code == 422
    assert client.post("/lab/orders", headers=auth("receptionist"), json={"patient_id": pid, "doctor": DOC,
                                                                          "test_ids": [tests["GLU"]["id"]]}).status_code == 403
    assert client.get("/lab/orders", headers=auth("cashier")).status_code == 403
    order = _order(client, auth, pid, test_ids=[tests["GLU"]["id"]]).json()
    item = order["items"][0]["id"]
    assert client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": []}).status_code == 422
    other = "00000000-0000-0000-0000-000000000000"
    assert client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"),
                      json={"results": [{"item_id": other, "value": 1}]}).status_code == 422
    cancelled = client.post(f"/lab/orders/{order['id']}/cancel", headers=auth("doctor")).json()
    assert cancelled["status"] == "Cancelled"
    assert client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": [{"item_id": item, "value": 5}]}).status_code == 409
    assert client.post(f"/lab/orders/{order['id']}/cancel", headers=auth("doctor")).status_code == 409
    assert [o["id"] for o in client.get("/lab/orders", params={"status": "Cancelled"}, headers=auth("doctor")).json()] == [order["id"]]
    audit = client.get("/security/audit", params={"entity_type": "lab_order", "limit": 50}, headers=auth("admin")).json()["items"]
    assert {"create", "update", "read"} <= {e["action"] for e in audit}


def test_catalog_management_admin_only(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    body = {"code": "xyz", "name": "Yangi ko'rsatkich", "unit": "U/L", "category": "Sinov", "ranges": [{"sex": "male", "high": 10}]}
    assert client.post("/lab/tests", headers=doc, json=body).status_code == 403
    created = client.post("/lab/tests", headers=admin, json=body)
    assert created.status_code == 201 and created.json()["code"] == "XYZ"
    assert client.post("/lab/tests", headers=admin, json={**body, "code": "Xyz"}).status_code == 409
    assert client.post("/lab/tests", headers=admin, json={**body, "code": "BAD", "ranges": [{"low": 5, "high": 1}]}).status_code == 422
    assert client.post("/lab/tests", headers=admin, json={**body, "code": "BAD2", "ranges": [{}]}).status_code == 422
    panel = client.post("/lab/panels", headers=admin, json={"name": "Sinov to'plami", "test_codes": ["xyz", "GLU"]})
    assert panel.status_code == 201 and panel.json()["test_codes"] == ["XYZ", "GLU"]
    assert client.post("/lab/panels", headers=admin, json={"name": "Noto'g'ri", "test_codes": ["NOPE"]}).status_code == 422
    assert client.put(f"/lab/tests/{created.json()['id']}", headers=admin, json={"is_active": False}).status_code == 200
    assert "XYZ" not in _tests(client, auth)


def _pdf_text(content: bytes) -> str:
    import io

    from pypdf import PdfReader

    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)


def test_pdf_contains_patient_results_reference_and_is_audited(client, auth):
    tests = _tests(client, auth)
    admin = auth("admin")
    pid = client.post("/patients", json={**NEW, "name": "Абдуллаев Ўктам", "gender": "male", "birth_date": "1990-01-01", "age": None},
                      headers=admin).json()["id"]
    order = _order(client, auth, pid, test_ids=[tests["HGB"]["id"], tests["GLU"]["id"]], notes="Och qoringa").json()
    client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"),
               json={"results": [{"item_id": order["items"][0]["id"], "value": 125}, {"item_id": order["items"][1]["id"], "value": 5.0}]})
    res = client.get(f"/lab/orders/{order['id']}/pdf", headers=auth("nurse"))
    assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF") and "inline" in res.headers["content-disposition"]
    text = _pdf_text(res.content)
    for needle in ("Gemoglobin", "125", "130 - 170", "Past", "Glyukoza", "5", "3.9 - 5.9", "Me'yorda", "Digital Clinic", "Och qoringa"):
        assert needle in text, needle
    assert "Абдуллаев" in text                                              # kirill DejaVu bilan
    assert client.get(f"/lab/orders/{order['id']}/pdf", headers=auth("cashier")).status_code == 403
    assert client.get("/lab/orders/00000000-0000-0000-0000-000000000000/pdf", headers=admin).status_code == 404
    audit = client.get("/security/audit", params={"entity_type": "lab_order", "limit": 50}, headers=admin).json()["items"]
    assert any(e["action"] == "read" and (e.get("details") or {}).get("pdf") for e in audit)


def test_pdf_pending_order_shows_dashes(client, auth):
    tests = _tests(client, auth)
    order = _order(client, auth, _setup(client, auth), test_ids=[tests["ALT"]["id"]]).json()
    text = _pdf_text(client.get(f"/lab/orders/{order['id']}/pdf", headers=auth("doctor")).content)
    assert "ALT" in text and "Kutilmoqda" in text
