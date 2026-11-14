"""Hisob-faktura bemor va sug'urta ulushiga bo'linishi (v1.9.26): qoplash foizi, shartnoma chegirmasi, limitlar, kafolat xati, to'lov va holat."""
from datetime import date, timedelta

import pytest

from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
D = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731
ZERO = "00000000-0000-0000-0000-000000000000"


def _service(client, h, name, price=100000):
    return client.post("/services", headers=h, json={"name": name, "price": price, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 12}).json()["id"]


@pytest.fixture
def world(client, auth):
    admin = auth("admin")
    insurer = client.post("/insurance/insurers", json={"name": "Hisob Sug'urta"}, headers=admin).json()
    a, b, c = _service(client, admin, "Xizmat A"), _service(client, admin, "Xizmat B"), _service(client, admin, "Qoplanmaydigan")
    contract = client.post("/insurance/contracts", headers=admin, json={
        "insurer_id": insurer["id"], "number": "HS-1", "valid_from": D(-100), "valid_to": D(200), "discount_percent": 10,
        "services": [{"service_id": a, "coverage_percent": 100}, {"service_id": b, "coverage_percent": 50}]}).json()
    pid = client.post("/patients", json={**NEW, "name": "Sug'urtalangan Bemor"}, headers=admin).json()["id"]
    pol = client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": contract["id"], "number": "P-100", "valid_from": D(-30), "valid_to": D(300)}).json()
    return admin, insurer, contract, (a, b, c), pid, pol


def _invoice(client, h, pid, lines, pol=None, letter=None, issue=True, **kw):
    body = {"patient_id": pid, "issue": issue, "lines": [{"service_id": s, "quantity": q} for s, q in lines], **kw}
    if pol:
        body["policy_id"] = pol["id"]
    if letter:
        body["guarantee_letter_id"] = letter["id"]
    return client.post("/invoices", headers=h, json=body)


def test_split_by_coverage_with_contract_discount_and_payment_status(client, auth, world):
    admin, insurer, contract, (a, b, c), pid, pol = world
    cashier = auth("cashier")
    res = _invoice(client, cashier, pid, [(a, 1), (b, 1), (c, 1)], pol)                              # 3 x 100000, shartnoma chegirmasi 10%
    assert res.status_code == 201, res.text
    inv = res.json()
    assert inv["subtotal"] == 300000 and inv["discount_total"] == 30000 and inv["total"] == 270000 and inv["discount_percent"] == 10
    assert inv["discount_reason"].startswith("Sug'urta shartnomasi HS-1")
    by = {ln["name"]: ln for ln in inv["lines"]}
    assert by["Xizmat A"]["net_total"] == 90000 and by["Xizmat A"]["insurer_amount"] == 90000                            # 100% qoplanadi
    assert by["Xizmat B"]["insurer_amount"] == 45000 and by["Qoplanmaydigan"]["insurer_amount"] == 0                      # 50% va qoplanmaydi
    assert (inv["insurer_total"], inv["patient_total"], inv["balance"]) == (135000, 135000, 135000)
    assert inv["policy_number"] == "P-100" and inv["insurer"] == "Hisob Sug'urta" and inv["status"] == "Issued"
    # to'lov faqat bemor ulushiga
    over = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 135001})
    assert over.status_code in (409, 422)
    part = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 100000})
    assert part.status_code == 201
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["status"] == "PartiallyPaid"
    rest = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"})                      # qoldiq = bemor ulushining qolgani
    assert rest.status_code == 201 and rest.json()["amount"] == 35000
    done = client.get(f"/invoices/{inv['id']}", headers=cashier).json()
    assert done["status"] == "Paid" and done["balance"] == 0 and done["paid_amount"] == 135000 and done["insurer_total"] == 135000   # sug'urta ulushi to'lanmagan qarz
    # fiskal chek bemor to'lovi bo'yicha: qatorlar yig'indisi to'langan summaga teng
    receipt = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()
    assert sum(p["amount"] for p in receipt) == 135000


def test_fully_insured_invoice_is_paid_for_patient_and_manual_discount_rejected(client, auth, world):
    admin, insurer, contract, (a, b, c), pid, pol = world
    cashier = auth("cashier")
    inv = _invoice(client, cashier, pid, [(a, 2)], pol).json()                                       # 100% qoplanadigan xizmat
    assert inv["total"] == 180000 and inv["insurer_total"] == 180000 and inv["patient_total"] == 0 and inv["status"] == "Paid" and inv["balance"] == 0
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code in (409, 422)    # bemor to'lovi yo'q
    for extra in ({"discount_percent": 5, "discount_reason": "qo'lda"}, {"discount_amount": 1000, "discount_reason": "qo'lda"}):
        assert _invoice(client, auth("admin"), pid, [(a, 1)], pol, **extra).status_code == 422
    body = {"patient_id": pid, "policy_id": pol["id"], "issue": True, "lines": [{"service_id": a, "quantity": 1, "discount_percent": 5}]}
    assert client.post("/invoices", headers=admin, json=body).status_code == 422
    plain = _invoice(client, cashier, pid, [(a, 1)]).json()                                          # polissiz oddiy hisob-faktura o'zgarmagan
    assert plain["insurer_total"] == 0 and plain["patient_total"] == 100000 and plain["policy_id"] is None


def test_policy_validation_limits_and_cancelled_invoice(client, auth, world):
    admin, insurer, contract, (a, b, c), pid, pol = world
    cashier = auth("cashier")
    other = client.post("/patients", json={**NEW, "name": "Boshqa Bemor"}, headers=admin).json()["id"]
    assert _invoice(client, cashier, other, [(a, 1)], pol).status_code == 422                        # polis boshqa bemorniki
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": a, "quantity": 1}], "policy_id": ZERO}).status_code == 422
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": a, "quantity": 1}], "guarantee_letter_id": ZERO}).status_code == 422
    # limitlar: bitta hisob-faktura 100000, yillik 150000
    client.put(f"/insurance/contracts/{contract['id']}", headers=admin, json={"per_visit_limit": 100000, "annual_limit": 150000})
    first = _invoice(client, cashier, pid, [(a, 1), (b, 1)], pol).json()                              # 180000 chegirmadan keyin: A 90000 + B 45000 = 135000 -> 100000 gacha
    assert first["insurer_total"] == 100000 and sum(ln["insurer_amount"] for ln in first["lines"]) == 100000            # qatorlarga proporsional
    second = _invoice(client, cashier, pid, [(a, 1)], pol).json()                                    # yillik qoldiq 50000
    assert second["insurer_total"] == 50000 and second["patient_total"] == 90000 - 50000
    third = _invoice(client, cashier, pid, [(a, 1)], pol).json()                                     # yillik limit tugagan
    assert third["insurer_total"] == 0 and third["patient_total"] == 90000
    cancel = client.post(f"/invoices/{second['id']}/cancel", headers=cashier, json={"reason": "xato yozildi"})        # bekor qilinsa limit qaytadi
    assert cancel.status_code == 200
    again = _invoice(client, cashier, pid, [(a, 1)], pol).json()
    assert again["insurer_total"] == 50000
    # shartnoma tugasa yangi hisob-faktura yo'q
    client.put(f"/insurance/contracts/{contract['id']}", headers=admin, json={"is_active": False})
    assert _invoice(client, cashier, pid, [(a, 1)], pol).status_code == 422


def test_guarantee_letter_required_limits_and_draft_update_issue(client, auth, world):
    admin, insurer, contract, (a, b, c), pid, pol = world
    cashier = auth("cashier")
    client.put(f"/insurance/contracts/{contract['id']}", headers=admin, json={"requires_guarantee": True})
    assert _invoice(client, cashier, pid, [(a, 1)], pol).status_code == 422                          # kafolat xati talab qilinadi
    letter = client.post("/insurance/guarantee-letters", headers=admin, json={"policy_id": pol["id"], "number": "GL-INV", "letter_date": D(0), "amount_limit": 120000,
                                                                              "service_ids": [a]}).json()
    inv = _invoice(client, cashier, pid, [(a, 1), (b, 1)], pol, letter).json()                       # xat faqat A xizmatini qamrab oladi
    by = {ln["name"]: ln for ln in inv["lines"]}
    assert by["Xizmat A"]["insurer_amount"] == 90000 and by["Xizmat B"]["insurer_amount"] == 0 and inv["guarantee_letter_number"] == "GL-INV"
    assert client.get(f"/insurance/guarantee-letters/{letter['id']}", headers=admin).json()["used_amount"] == 90000
    assert client.get(f"/insurance/guarantee-letters/{letter['id']}", headers=admin).json()["remaining"] == 30000
    second = _invoice(client, cashier, pid, [(a, 1)], pol, letter).json()                            # xat qoldig'i 30000
    assert second["insurer_total"] == 30000
    exhausted = client.get(f"/insurance/guarantee-letters/{letter['id']}", headers=admin).json()
    assert exhausted["state"] == "Exhausted" and exhausted["remaining"] == 0
    assert _invoice(client, cashier, pid, [(a, 1)], pol, letter).status_code == 422                  # tugagan xat bilan yozib bo'lmaydi
    assert client.put(f"/insurance/guarantee-letters/{letter['id']}", headers=admin, json={"amount_limit": 100000}).status_code == 422   # ishlatilgandan kam
    # qoralama: yaratish, o'zgartirish, chiqarishda qayta hisoblanadi (limit 400000, ishlatilgan 120000)
    up = client.put(f"/insurance/guarantee-letters/{letter['id']}", headers=admin, json={"amount_limit": 400000})
    assert up.status_code == 200, up.text
    draft_res = _invoice(client, cashier, pid, [(a, 1)], pol, letter, issue=False)
    assert draft_res.status_code == 201, draft_res.text
    draft = draft_res.json()
    assert draft["status"] == "Draft" and draft["insurer_total"] == 90000
    upd = client.put(f"/invoices/{draft['id']}", headers=cashier, json={"lines": [{"service_id": a, "quantity": 2}], "policy_id": pol["id"], "guarantee_letter_id": letter["id"]})
    assert upd.status_code == 200 and upd.json()["insurer_total"] == 180000                           # o'zi hisobga olinmaydi
    other = _invoice(client, cashier, pid, [(a, 2)], pol, letter).json()                             # qoralama ulushi band: qolgan 100000
    assert other["insurer_total"] == 100000
    issued = client.post(f"/invoices/{draft['id']}/issue", headers=cashier).json()
    assert issued["status"] == "Paid" and issued["patient_total"] == 0 and issued["insurer_total"] == 180000                        # chiqarishda qayta hisoblandi (o'zini hisobga olmasdan)
    assert client.get(f"/insurance/guarantee-letters/{letter['id']}", headers=admin).json()["used_amount"] == 400000
    client.put(f"/insurance/contracts/{contract['id']}", headers=admin, json={"requires_guarantee": False})
    d2 = _invoice(client, cashier, pid, [(a, 1)], pol, issue=False).json()
    assert d2["insurer_total"] == 90000
    noins = client.put(f"/invoices/{d2['id']}", headers=cashier, json={"lines": [{"service_id": a, "quantity": 1}]})
    assert noins.status_code == 200 and noins.json()["insurer_total"] == 0 and noins.json()["policy_id"] is None            # polissiz yangilansa sug'urta olib tashlanadi
