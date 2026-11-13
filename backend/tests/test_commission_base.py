from datetime import date, timedelta

import pytest

from tests.test_commissions import DOC1, _doctor, _entries, _invoice, _pay, _service

TODAY = date.today()
pytestmark = pytest.mark.usefixtures("desk")


def _rule(client, auth, **kw):
    body = {"kind": "Percent", "percent": 10, "valid_from": (TODAY - timedelta(days=30)).isoformat(), **kw}
    res = client.post("/commission-rules", headers=auth("admin"), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _paid(client, auth, svc, d1, **kw):
    inv = _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}], **kw)
    _pay(client, auth, inv)
    return inv


def test_default_is_after_discount_without_vat(client, auth):
    assert client.get("/settings/finance", headers=auth("admin")).json()["commission_base"] == "NetOfVat"
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Asos xizmati", 112000, vat=12)
    rule = _rule(client, auth)
    assert rule["base"] is None                                                   # sozlama bo'yicha
    _paid(client, auth, svc, d1)
    e = _entries(client, auth)[0]
    assert (e["base_kind"], e["base_amount"], e["amount"]) == ("NetOfVat", 100000.0, 10000.0)            # 112000 - 12000 QQS
    # chegirmadan keyin: 10% chegirma -> 100800, QQS 10800 -> 90000
    _paid(client, auth, _service(client, auth, "Asos chegirmali", 112000), d1, discount_percent=10, discount_reason="Doimiy mijoz")
    e2 = _entries(client, auth)[-1]
    assert e2["base_amount"] == 90000.0 and e2["amount"] == 9000.0


def test_setting_change_affects_only_later_accruals_and_rule_override_wins(client, auth):
    admin = auth("admin")
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Sozlama xizmati", 112000, vat=12)
    _rule(client, auth)
    _paid(client, auth, svc, d1)                                                   # NetOfVat
    assert client.put("/settings/finance", headers=admin, json={"discount_limit_percent": 10, "commission_base": "WithVat"}).json()["commission_base"] == "WithVat"
    svc2 = _service(client, auth, "Sozlama 2", 112000, vat=12)
    _paid(client, auth, svc2, d1)                                                  # WithVat
    first, second = _entries(client, auth)
    assert (first["base_kind"], first["amount"]) == ("NetOfVat", 10000.0)          # eski yozuv o'zgarmadi
    assert (second["base_kind"], second["amount"]) == ("WithVat", 11200.0)
    # qoidada aniq ko'rsatilgan asos sozlamadan ustun
    svc3 = _service(client, auth, "Sozlama 3", 112000, vat=12)
    _rule(client, auth, service_id=svc3["id"], base="NetOfVat")
    _paid(client, auth, svc3, d1)
    third = [e for e in _entries(client, auth) if e["service"] == "Sozlama 3"][0]
    assert (third["base_kind"], third["amount"]) == ("NetOfVat", 10000.0)
    assert DOC1


def test_setting_validation_audit_and_permissions(client, auth):
    assert client.put("/settings/finance", headers=auth("admin"), json={"discount_limit_percent": 10, "commission_base": "Gross"}).status_code == 422
    assert client.put("/settings/finance", headers=auth("cashier"), json={"discount_limit_percent": 10, "commission_base": "WithVat"}).status_code == 403
    client.put("/settings/finance", headers=auth("admin"), json={"discount_limit_percent": 10, "commission_base": "WithVat"})
    audit = client.get("/security/audit", params={"entity_type": "settings", "limit": 5}, headers=auth("admin")).json()["items"]
    assert audit[0]["details"]["commission_base"] == {"from": "NetOfVat", "to": "WithVat"}


def test_reversal_keeps_base_kind_of_accrual(client, auth):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, "Qaytarish asosi", 112000, vat=12)
    _rule(client, auth)
    inv = _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}])
    pay = _pay(client, auth, inv)
    client.put("/settings/finance", headers=auth("admin"), json={"discount_limit_percent": 10, "commission_base": "WithVat"})
    client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "To'liq qaytarish"})
    entries = _entries(client, auth)
    assert [(e["kind"], e["base_kind"], e["amount"]) for e in entries] == [("Accrual", "NetOfVat", 10000.0), ("Reversal", "NetOfVat", -10000.0)]
