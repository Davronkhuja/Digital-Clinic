"""Shifokor foizi sug'urtali hisob-fakturada (v2.0.1): standart "to'liq summadan": bemor ulushidan darhol, sug'urta ulushidan kompaniya to'lagach;
"PatientOnly" sozlamada faqat bemor to'lovidan. Kompaniya to'lovi bekor qilinsa foiz teskari yoziladi."""
from datetime import date, timedelta

import pytest

from tests.test_commissions import _doctor, _entries, _pay, _rule, _service
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
D = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731


def _insured_invoice(client, auth, tag, doctor, price=100000, qty=2, pct=70):
    admin = auth("admin")
    ins = client.post("/insurance/insurers", json={"name": f"Foiz Sug'urta {tag}", "tin": "300777888"}, headers=admin).json()
    svc = _service(client, auth, f"Foiz sug'urta xizmati {tag}", price)
    contract = client.post("/insurance/contracts", headers=admin, json={"insurer_id": ins["id"], "number": f"FS-{tag}", "valid_from": D(-30), "valid_to": D(300),
                                                                         "services": [{"service_id": svc["id"], "coverage_percent": pct}]}).json()
    pid = client.post("/patients", json={**NEW, "name": f"Foiz Sug'urta Bemor {tag}"}, headers=admin).json()["id"]
    pol = client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": contract["id"], "number": f"FP-{tag}", "valid_from": D(-20)}).json()
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "policy_id": pol["id"], "issue": True,
                                                                  "lines": [{"service_id": svc["id"], "doctor_id": doctor, "quantity": qty}]}).json()
    assert inv["insurer_total"] == price * qty * pct / 100, inv
    return ins, inv


def _mine(client, auth, inv):
    return [e for e in _entries(client, auth) if e["invoice_number"] == inv["number"]]


def test_full_amount_patient_share_now_insurer_share_after_company_pays(client, auth):
    admin = auth("admin")
    assert client.get("/settings/finance", headers=admin).json()["commission_scope"] == "FullAmount"        # standart
    doctor = _doctor(client, auth)
    _rule(client, auth, percent=10)                                                                         # QQS bilan
    ins, inv = _insured_invoice(client, auth, "A", doctor)                                                  # 200000: bemor 60000, kompaniya 140000
    _pay(client, auth, inv)
    got = _mine(client, auth, inv)
    assert [(e["source"], e["amount"]) for e in got] == [("Patient", 6000.0)]                               # bemor ulushidan darhol
    pay1 = client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 70000}).json()
    got = _mine(client, auth, inv)
    assert sorted((e["source"], e["kind"], e["amount"]) for e in got) == [("Insurer", "Accrual", 7000.0), ("Patient", "Accrual", 6000.0)]
    ins_entry = next(e for e in got if e["source"] == "Insurer")
    assert ins_entry["payment_id"] is None and ins_entry["base_amount"] == 70000.0 and ins_entry["doctor_id"] == doctor
    pay2 = client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 70000}).json()
    assert sum(e["amount"] for e in _mine(client, auth, inv)) == 20000.0                                    # 10% x 200000: to'liq summa
    # ortiqcha to'lov qo'shimcha foiz bermaydi (faqat shu hisob-fakturaning sug'urta ulushi)
    client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 50000})
    assert sum(e["amount"] for e in _mine(client, auth, inv)) == 20000.0
    # xato to'lovni bekor qilish foizni teskari yozadi
    assert client.post(f"/insurance/payments/{pay2['id']}/reverse", headers=admin, json={"reason": "noto'g'ri summa"}).status_code == 200
    after = _mine(client, auth, inv)
    assert sum(e["amount"] for e in after) == 18000.0                                                       # 70000+50000=120000 -> 12000 + bemor 6000
    # ... yana bekor: 70000 -> 7000 qoladi
    extra = next(p for p in client.get("/insurance/payments", params={"insurer_id": ins["id"]}, headers=admin).json() if p["amount"] == 50000)
    client.post(f"/insurance/payments/{extra['id']}/reverse", headers=admin, json={"reason": "yana xato"})
    final = _mine(client, auth, inv)
    assert round(sum(e["amount"] for e in final if e["source"] == "Insurer"), 2) == 7000.0 and any(e["kind"] == "Reversal" for e in final)
    assert pay1["amount"] == 70000
    # oylik hisobda sof foiz = bemor 6000 + kompaniya 7000
    rep = client.get("/commissions/report", params={"month": date.today().strftime("%Y-%m"), "doctor_id": doctor}, headers=admin).json()
    assert rep["doctors"][0]["net"] >= 13000.0


def test_patient_only_setting_skips_insurer_share(client, auth):
    admin = auth("admin")
    doctor = _doctor(client, auth)
    _rule(client, auth, percent=10)
    put = client.put("/settings/finance", headers=admin, json={"discount_limit_percent": 10, "commission_base": "NetOfVat", "commission_scope": "PatientOnly"})
    assert put.status_code == 200 and put.json()["commission_scope"] == "PatientOnly"
    try:
        ins, inv = _insured_invoice(client, auth, "B", doctor)
        _pay(client, auth, inv)
        client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 140000})
        assert [e["source"] for e in _mine(client, auth, inv)] == ["Patient"]                               # faqat bemor to'lovidan
        # sozlamani yuborilmasa o'zgarmaydi
        keep = client.put("/settings/finance", headers=admin, json={"discount_limit_percent": 10, "commission_base": "NetOfVat"}).json()
        assert keep["commission_scope"] == "PatientOnly"
        assert client.put("/settings/finance", headers=admin, json={"discount_limit_percent": 10, "commission_scope": "Gross"}).status_code == 422
    finally:
        client.put("/settings/finance", headers=admin, json={"discount_limit_percent": 10, "commission_base": "NetOfVat", "commission_scope": "FullAmount"})
