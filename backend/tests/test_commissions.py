from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.test_patients import NEW

DOC1, DOC2 = "Dr. Behruz Rustamov", "Dr. Zulfiya Karimova"
TODAY = date.today()


pytestmark = pytest.mark.usefixtures("desk")


def _doctor(client, auth, name=DOC1):
    return next(s["id"] for s in client.get("/staff", headers=auth("admin")).json() if s["name"] == name)


def _service(client, auth, name, price, vat=12):
    return client.post("/services", headers=auth("admin"), json={"name": name, "price": price, "mxik": "09302001001000000",
                                                                "package_code": "1500364", "vat_percent": vat}).json()


def _rule(client, auth, **kw):
    body = {"kind": "Percent", "percent": 10, "valid_from": (TODAY - timedelta(days=30)).isoformat(), **kw}
    res = client.post("/commission-rules", headers=auth("admin"), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _invoice(client, auth, lines, doctor_id=None, **kw):
    pid = client.post("/patients", json={**NEW, "name": "Foiz Bemor"}, headers=auth("admin")).json()["id"]
    return client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "doctor_id": doctor_id, "lines": lines, "issue": True, **kw}).json()


def _pay(client, auth, inv, amount=None, method="Cash"):
    body = {"method": method, **({"amount": amount} if amount else {})}
    res = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _entries(client, auth, **params):
    return client.get("/commissions/entries", params={"month": TODAY.strftime("%Y-%m"), **params}, headers=auth("admin")).json()


def test_percent_commission_on_payment_and_rule_resolution(client, auth):
    d1, d2 = _doctor(client, auth), _doctor(client, auth, DOC2)
    cons, xray = _service(client, auth, "Konsultatsiya", 100000), _service(client, auth, "Rentgen", 200000)
    _rule(client, auth, percent=10)                                              # umumiy
    _rule(client, auth, doctor_id=d1, percent=20)                                # shifokor
    _rule(client, auth, service_id=xray["id"], percent=30)                       # xizmat
    _rule(client, auth, doctor_id=d1, service_id=xray["id"], percent=40)         # shifokor + xizmat
    inv = _invoice(client, auth, [{"service_id": cons["id"], "doctor_id": d1}, {"service_id": xray["id"], "doctor_id": d1},
                                  {"service_id": cons["id"], "doctor_id": d2}, {"service_id": xray["id"], "doctor_id": d2}])
    assert _entries(client, auth) == []                                          # to'lovgacha foiz yo'q
    _pay(client, auth, inv)
    got = {(e["doctor"], e["service"]): (e["rule_percent"], e["amount"], e["base_amount"]) for e in _entries(client, auth)}
    assert got[(DOC1, "Konsultatsiya")] == (20.0, 20000.0, 100000.0)
    assert got[(DOC1, "Rentgen")] == (40.0, 80000.0, 200000.0)                   # eng aniq qoida
    assert got[(DOC2, "Konsultatsiya")] == (10.0, 10000.0, 100000.0)             # umumiy
    assert got[(DOC2, "Rentgen")] == (30.0, 60000.0, 200000.0)                   # xizmat bo'yicha


def test_fixed_amount_per_unit_and_vat_base_and_validity(client, auth):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Fiks xizmat", 112000, vat=12)
    _rule(client, auth, doctor_id=d1, service_id=svc["id"], kind="Fixed", percent=None, fixed_amount=15000)
    inv = _invoice(client, auth, [{"service_id": svc["id"], "quantity": 3, "doctor_id": d1}])
    _pay(client, auth, inv)
    e = _entries(client, auth)[0]
    assert e["rule_kind"] == "Fixed" and e["amount"] == 45000.0                  # 3 birlik * 15000
    # QQSsiz asos
    svc2 = _service(client, auth, "QQS asosli", 112000, vat=12)
    _rule(client, auth, service_id=svc2["id"], percent=10, base="NetOfVat")
    inv2 = _invoice(client, auth, [{"service_id": svc2["id"], "doctor_id": d1}])
    _pay(client, auth, inv2)
    e2 = [x for x in _entries(client, auth) if x["service"] == "QQS asosli"][0]
    assert e2["base_amount"] == 100000.0 and e2["amount"] == 10000.0             # 112000 - 12000 QQS
    # amal qilish sanasi: kelajak va tugagan qoidalar qo'llanmaydi
    svc3 = _service(client, auth, "Sanali", 50000)
    _rule(client, auth, service_id=svc3["id"], percent=50, valid_from=(TODAY + timedelta(days=5)).isoformat())
    _rule(client, auth, service_id=svc3["id"], percent=60, valid_from=(TODAY - timedelta(days=60)).isoformat(),
          valid_to=(TODAY - timedelta(days=1)).isoformat())
    inv3 = _invoice(client, auth, [{"service_id": svc3["id"], "doctor_id": d1}])
    _pay(client, auth, inv3)
    assert [x for x in _entries(client, auth) if x["service"] == "Sanali"] == []              # sanasi to'g'ri qoida yo'q
    _rule(client, auth, service_id=svc3["id"], percent=25)
    inv4 = _invoice(client, auth, [{"service_id": svc3["id"], "doctor_id": d1}])
    _pay(client, auth, inv4)
    e4 = [x for x in _entries(client, auth) if x["service"] == "Sanali"]
    assert len(e4) == 1 and e4[0]["rule_percent"] == 25.0                                      # kelajak (50%) va tugagan (60%) emas


def test_no_rule_no_doctor_no_entry_and_discount_reduces_base(client, auth):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Chegirmali", 100000)
    inv = _invoice(client, auth, [{"service_id": svc["id"]}])                       # ijrochi yo'q
    _pay(client, auth, inv)
    assert _entries(client, auth) == []
    _rule(client, auth, percent=10)
    inv2 = _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}], discount_percent=10, discount_reason="Doimiy mijoz")
    _pay(client, auth, inv2)
    e = _entries(client, auth)[0]
    assert e["base_amount"] == 90000.0 and e["amount"] == 9000.0                    # chegirmadan keyingi to'langan summa


def test_partial_payments_accrue_proportionally_and_sum_to_full(client, auth):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Qisman", 100000)
    _rule(client, auth, percent=10)
    inv = _invoice(client, auth, [{"service_id": svc["id"], "quantity": 3, "doctor_id": d1}])
    _pay(client, auth, inv, amount=100000)
    _pay(client, auth, inv, amount=200000)
    entries = _entries(client, auth)
    assert [e["amount"] for e in entries] == [10000.0, 20000.0] and sum(e["amount"] for e in entries) == 30000.0


def test_refund_reverses_commission_proportionally(client, auth):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Qaytariladigan", 100000)
    _rule(client, auth, percent=10)
    inv = _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}])
    pay = _pay(client, auth, inv)
    client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Qisman qaytarish", "amount": 25000})
    client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Yana qismi", "amount": 25000})
    entries = _entries(client, auth)
    assert [(e["kind"], e["amount"]) for e in entries] == [("Accrual", 10000.0), ("Reversal", -2500.0), ("Reversal", -2500.0)]
    assert entries[1]["refund_id"] and entries[1]["base_amount"] == -25000.0
    client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Qolgani to'liq"})
    entries = _entries(client, auth)
    assert round(sum(e["amount"] for e in entries), 2) == 0.0 and entries[-1]["amount"] == -5000.0
    report = client.get("/commissions/report", params={"month": TODAY.strftime("%Y-%m")}, headers=auth("admin")).json()
    row = report["doctors"][0]
    assert (row["accrued"], row["reversed"], row["net"]) == (10000.0, 10000.0, 0.0) and report["total_net"] == 0.0


def test_rounding_reversal_never_exceeds_accrual(client, auth):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Yaxlitlash", 100003)
    _rule(client, auth, percent=7)
    inv = _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}])
    pay = _pay(client, auth, inv)
    for amount in (33334.01, 33334.01, 33334.01, 100003 - 3 * 33334.01):
        client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Bo'laklab", "amount": round(amount, 2)})
    entries = _entries(client, auth)
    accrual = entries[0]["amount"]
    total_rev = -sum(e["amount"] for e in entries[1:])
    assert Decimal(str(round(total_rev, 2))) == Decimal(str(accrual)) and all(e["amount"] < 0 for e in entries[1:])


def test_rule_validation_permissions_and_audit(client, auth):
    admin, doctor = auth("admin"), auth("doctor")
    base = {"valid_from": TODAY.isoformat()}
    for bad in ({"kind": "Percent"}, {"kind": "Percent", "percent": 0}, {"kind": "Percent", "percent": 101},
                {"kind": "Percent", "percent": 10, "fixed_amount": 100}, {"kind": "Fixed", "percent": 10},
                {"kind": "Fixed"}, {"kind": "Fixed", "fixed_amount": -5}, {"kind": "Percent", "percent": 10, "valid_to": "2000-01-01"}):
        assert client.post("/commission-rules", headers=admin, json={**base, **bad}).status_code == 422, bad
    assert client.post("/commission-rules", headers=admin, json={**base, "kind": "Percent", "percent": 10,
                                                                 "doctor_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    assert client.post("/commission-rules", headers=doctor, json={**base, "kind": "Percent", "percent": 10}).status_code == 403
    assert client.get("/commission-rules", headers=doctor).status_code == 403
    r = _rule(client, auth, percent=12)
    assert client.put(f"/commission-rules/{r['id']}", headers=admin, json={**base, "kind": "Percent", "percent": 15, "is_active": False}).json()["is_active"] is False
    assert client.get("/commission-rules", headers=admin).json() == []
    assert len(client.get("/commission-rules", params={"include_inactive": True}, headers=admin).json()) == 1
    audit = client.get("/security/audit", params={"entity_type": "commission_rule", "limit": 10}, headers=admin).json()["items"]
    assert {"create", "update"} <= {e["action"] for e in audit}


def test_doctor_sees_only_own_and_month_settlement_locks(client, auth):
    d1, d2 = _doctor(client, auth), _doctor(client, auth, DOC2)
    svc = _service(client, auth, "Hisob-kitob", 100000)
    _rule(client, auth, percent=10)
    inv = _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}, {"service_id": svc["id"], "doctor_id": d2}])
    pay = _pay(client, auth, inv)
    month = TODAY.strftime("%Y-%m")
    mine = client.get("/commissions/report", params={"month": month}, headers=auth("doctor")).json()                  # Rustamov
    assert [d["doctor"] for d in mine["doctors"]] == [DOC1] and mine["total_net"] == 10000.0
    assert client.get("/commissions/report", params={"month": month, "doctor_id": d2}, headers=auth("doctor")).status_code == 403
    assert [e["doctor"] for e in client.get("/commissions/entries", params={"month": month}, headers=auth("doctor")).json()] == [DOC1]
    assert client.get("/commissions/report", params={"month": month}, headers=auth("cashier")).status_code == 403
    assert client.get("/commissions/report", params={"month": "2026-13"}, headers=auth("admin")).status_code == 422
    assert len(client.get("/commissions/report", params={"month": month}, headers=auth("admin")).json()["doctors"]) == 2
    # yopish
    assert client.post("/commissions/settle", headers=auth("doctor"), json={"month": month, "doctor_id": d1}).status_code == 403
    assert client.post("/commissions/settle", headers=auth("admin"), json={"month": (TODAY.replace(day=1) + timedelta(days=40)).strftime("%Y-%m"),
                                                                            "doctor_id": d1}).status_code == 422       # kelajak
    s = client.post("/commissions/settle", headers=auth("admin"), json={"month": month, "doctor_id": d1})
    assert s.status_code == 201 and s.json()["amount"] == 10000.0 and s.json()["entries_count"] == 1
    assert client.post("/commissions/settle", headers=auth("admin"), json={"month": month, "doctor_id": d1}).status_code == 409
    rep = {d["doctor"]: d for d in client.get("/commissions/report", params={"month": month}, headers=auth("admin")).json()["doctors"]}
    assert rep[DOC1]["settled"] is True and rep[DOC1]["settlement_id"] == s.json()["id"] and rep[DOC2]["settled"] is False
    assert [x["month"] for x in client.get("/commissions/settlements", headers=auth("doctor")).json()] == [month]
    # yopilgandan keyingi qaytarish: yangi (yopilmagan) manfiy yozuv
    client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Yopilgandan keyin qaytarish", "amount": 100000})
    after = [e for e in _entries(client, auth) if e["kind"] == "Reversal"]
    assert len(after) == 2 and all(not e["settled"] for e in after)
