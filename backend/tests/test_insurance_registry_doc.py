"""Sug'urta reyestri hujjati (v2.0.3): Draft (jonli) -> Sent (qotgan, Excel saqlanadi, o'zgarmas) -> Reconciled; kompaniya to'lovi reyestrga bog'lanadi;
yuborilgandan keyin o'zgargan hisob-faktura keyingi reyestrga tuzatish qatori bo'lib tushadi."""
import hashlib
import io
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook

from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
D = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731
ZERO = "00000000-0000-0000-0000-000000000000"
THIS = date.today().strftime("%Y-%m")
NEXT = (date.today().replace(day=1) + timedelta(days=32)).strftime("%Y-%m")


@pytest.fixture
def world(client, auth):
    admin = auth("admin")
    ins = client.post("/insurance/insurers", json={"name": "Hujjat Sug'urta", "tin": "300999111", "payment_days": 20}, headers=admin).json()
    svc = client.post("/services", headers=admin, json={"name": "Hujjat xizmati", "price": 100000, "mxik": "09302001001000000", "package_code": "1500364",
                                                       "vat_percent": 12}).json()["id"]
    contract = client.post("/insurance/contracts", headers=admin, json={"insurer_id": ins["id"], "number": "HJ-1", "valid_from": D(-400), "valid_to": D(300),
                                                                         "services": [{"service_id": svc, "coverage_percent": 70}]}).json()
    pid = client.post("/patients", json={**NEW, "name": "Hujjat Bemor"}, headers=admin).json()["id"]
    pol = client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": contract["id"], "number": "HP-1", "valid_from": D(-300)}).json()
    return admin, ins, svc, pid, pol


def _inv(client, auth, svc, pid, pol, qty):
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "policy_id": pol["id"], "issue": True, "lines": [{"service_id": svc, "quantity": qty}]}).json()
    assert inv["insurer_total"] == 70000 * qty, inv      # 70%: hisob-faktura bemor ulushi bilan ochiq qoladi
    return inv


def test_draft_send_freeze_corrections_and_reconcile(client, auth, world):
    admin, ins, svc, pid, pol = world
    a, b = _inv(client, auth, svc, pid, pol, 1), _inv(client, auth, svc, pid, pol, 2)
    # 1. Draft: jonli hisob
    res = client.post("/insurance/registries", json={"insurer_id": ins["id"], "month": THIS}, headers=admin)
    assert res.status_code == 201, res.text
    reg = res.json()
    assert reg["status"] == "Draft" and reg["number"].startswith(f"REE-{THIS.replace('-', '')}-") and reg["insurer_total"] == 210000 and reg["lines_count"] == 2
    assert {r["kind"] for r in reg["rows"]} == {"Original"} and reg["balance"] == 210000 and reg["paid"] == 0
    assert client.post("/insurance/registries", json={"insurer_id": ins["id"], "month": THIS}, headers=admin).status_code == 409           # bitta oy - bitta hujjat
    assert client.post("/insurance/registries", json={"insurer_id": ins["id"], "month": "2026-13"}, headers=admin).status_code == 422
    assert client.post("/insurance/registries", json={"insurer_id": ZERO, "month": THIS}, headers=admin).status_code == 422
    assert client.post("/insurance/registries", json={"insurer_id": ins["id"], "month": NEXT}, headers=auth("cashier")).status_code == 403
    assert client.get("/insurance/registries", headers=auth("cashier")).status_code == 200
    draft_xlsx = client.get(f"/insurance/registries/{reg['id']}/file", headers=admin)
    assert load_workbook(io.BytesIO(draft_xlsx.content)).sheetnames == ["Reyestr", "Xizmatlar bo'yicha"]
    assert client.post(f"/insurance/registries/{reg['id']}/reconcile", json={}, headers=admin).status_code == 409                          # Draft solishtirilmaydi
    # Draft jonli: yangi hisob-faktura darhol qatorga tushadi
    c = _inv(client, auth, svc, pid, pol, 1)
    assert client.get(f"/insurance/registries/{reg['id']}", headers=admin).json()["insurer_total"] == 280000
    assert client.post(f"/invoices/{c['id']}/cancel", json={"reason": "xato yozilgan"}, headers=admin).status_code == 200
    assert client.get(f"/insurance/registries/{reg['id']}", headers=admin).json()["insurer_total"] == 210000
    # 2. Yuborish: qotadi, Excel saqlanadi
    sent = client.post(f"/insurance/registries/{reg['id']}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    sent = sent.json()
    assert sent["status"] == "Sent" and sent["insurer_total"] == 210000 and sent["sent_at"] and sent["file_sha256"] and len(sent["rows"]) == 2
    file1 = client.get(f"/insurance/registries/{reg['id']}/file", headers=admin)
    assert hashlib.sha256(file1.content).hexdigest() == sent["file_sha256"]
    ws = load_workbook(io.BytesIO(file1.content))["Reyestr"]
    assert ws["A1"].value == f"Xizmatlar reyestri № {reg['number']}"
    assert client.post(f"/insurance/registries/{reg['id']}/send", headers=admin).status_code == 409                                           # qayta yuborilmaydi
    # 3. Yuborilgandan keyin: B bekor qilinadi, C2 kech chiqariladi -> hujjat o'zgarmaydi
    assert client.post(f"/invoices/{b['id']}/cancel", json={"reason": "bemor rad etdi"}, headers=admin).status_code == 200
    c2 = _inv(client, auth, svc, pid, pol, 3)
    again = client.get(f"/insurance/registries/{reg['id']}", headers=admin).json()
    assert again["insurer_total"] == 210000 and again["rows"] == sent["rows"]
    assert client.get(f"/insurance/registries/{reg['id']}/file", headers=admin).content == file1.content
    # 4. Keyingi reyestr: B uchun manfiy tuzatish, C2 yangi qator
    nxt = client.post("/insurance/registries", json={"insurer_id": ins["id"], "month": NEXT}, headers=admin).json()
    kinds = {(r["invoice"], r["kind"]): r for r in nxt["rows"]}
    assert set(kinds) == {(b["number"], "Correction"), (c2["number"], "Original")}
    corr = kinds[(b["number"], "Correction")]
    assert (corr["qty"], corr["line_total"], corr["insurer_amount"], corr["patient_amount"]) == (-2, -200000, -140000, -60000) and corr["service"].startswith("Tuzatish:")
    assert nxt["insurer_total"] == 70000 and nxt["corrections"] == 1      # +210000 - 140000
    # 5. Kompaniya to'lovi reyestrga bog'lanadi
    pay_body = {"insurer_id": ins["id"], "amount": 100000, "reference": "RG-1"}
    assert client.post("/insurance/payments", json={**pay_body, "registry_id": nxt["id"]}, headers=admin).status_code == 409                    # Draft ga emas
    other = client.post("/insurance/insurers", json={"name": "Boshqa Hujjat"}, headers=admin).json()
    assert client.post("/insurance/payments", json={**pay_body, "insurer_id": other["id"], "registry_id": reg["id"]}, headers=admin).status_code == 422
    p1 = client.post("/insurance/payments", json={**pay_body, "registry_id": reg["id"]}, headers=admin)
    assert p1.status_code == 201 and p1.json()["registry_id"] == reg["id"]
    state = client.get(f"/insurance/registries/{reg['id']}", headers=admin).json()
    assert (state["paid"], state["balance"]) == (100000, 110000)
    # 6. Solishtirish: to'lov yetmasa izoh majburiy
    assert client.post(f"/insurance/registries/{reg['id']}/reconcile", json={}, headers=admin).status_code == 422
    assert client.post(f"/insurance/registries/{reg['id']}/reconcile", json={"note": "xo"}, headers=admin).status_code == 422
    assert client.post(f"/insurance/registries/{reg['id']}/reconcile", json={}, headers=auth("cashier")).status_code == 403
    done = client.post(f"/insurance/registries/{reg['id']}/reconcile", json={"note": "Kompaniya 110000 ni keyingi oyda to'laydi"}, headers=admin)
    assert done.status_code == 200 and done.json()["status"] == "Reconciled" and done.json()["reconcile_note"] and done.json()["rows"] == sent["rows"]
    assert client.post(f"/insurance/registries/{reg['id']}/reconcile", json={"note": "yana"}, headers=admin).status_code == 409
    assert client.post(f"/insurance/payments/{p1.json()['id']}/reverse", json={"reason": "noto'g'ri summa"}, headers=admin).status_code == 409   # qotgan reyestr
    assert client.post("/insurance/payments", json={**pay_body, "registry_id": reg["id"]}, headers=admin).status_code == 409                    # Reconciled ga qo'shilmaydi
    # 7. To'liq to'langan reyestr izohsiz solishtiriladi; ro'yxat filtri
    client.post(f"/insurance/registries/{nxt['id']}/send", headers=admin)
    nxt_pay = client.post("/insurance/payments", json={**pay_body, "amount": 70000, "registry_id": nxt["id"]}, headers=admin)
    assert nxt_pay.status_code == 201
    assert client.post(f"/insurance/registries/{nxt['id']}/reconcile", json={}, headers=admin).json()["status"] == "Reconciled"
    listed = client.get("/insurance/registries", params={"insurer_id": ins["id"], "status": "Reconciled"}, headers=admin).json()
    assert {r["number"] for r in listed} == {reg["number"], nxt["number"]}
    assert client.get(f"/insurance/registries/{ZERO}", headers=admin).status_code == 404
    assert client.get("/insurance/registries", params={"status": "Bogus"}, headers=admin).status_code == 422
    assert a["number"] in {r["invoice"] for r in sent["rows"]}


def test_empty_registry_cannot_be_sent(client, auth, world):
    admin, ins, *_ = world
    reg = client.post("/insurance/registries", json={"insurer_id": ins["id"], "month": THIS}, headers=admin).json()
    assert reg["lines_count"] == 0 and client.post(f"/insurance/registries/{reg['id']}/send", headers=admin).status_code == 409
