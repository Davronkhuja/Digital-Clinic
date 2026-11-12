from decimal import Decimal

import pytest

from app.models import Service
from app.services.invoicing import LineInput, compute
from app.services.money import format_sum, from_tiyin, q2, to_tiyin
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def _svc(price, vat=Decimal("12")):
    return Service(name="x", price=Decimal(str(price)), mxik="1" * 17, package_code="1", vat_percent=vat)


def test_money_conversions_single_place():
    assert to_tiyin(Decimal("150000.50")) == 15000050 and to_tiyin(0) == 0 and to_tiyin("0.01") == 1
    assert from_tiyin(15000050) == Decimal("150000.50") and from_tiyin(1) == Decimal("0.01")
    with pytest.raises(ValueError):
        to_tiyin(Decimal("1.005"))                                           # tiyindan kichik kasr
    with pytest.raises(ValueError):
        from_tiyin(1.5)
    assert q2("2.675") == Decimal("2.68") and q2(Decimal("2.665")) == Decimal("2.67")        # ROUND_HALF_UP
    assert format_sum(Decimal("150000")) == "150000.00"
    assert from_tiyin(to_tiyin(Decimal("123456.78"))) == Decimal("123456.78")


def test_compute_vat_inclusive_and_no_discount():
    c = compute([LineInput(_svc(112000), 1), LineInput(_svc(50000, Decimal("0")), 2)], None, None)
    assert (c.subtotal, c.discount_total, c.total) == (Decimal("212000.00"),) + (Decimal("0.00"), Decimal("212000.00"))
    assert [ln.vat_amount for ln in c.lines] == [Decimal("12000.00"), Decimal("0.00")]          # 112000 * 12/112
    assert c.vat_total == Decimal("12000.00")


def test_compute_line_and_invoice_discount_allocation_sums_exactly():
    lines = [LineInput(_svc(100000), 1, discount_percent=Decimal("10")), LineInput(_svc(33333.33), 3), LineInput(_svc(7777.77), 1)]
    c = compute(lines, Decimal("5"), None)
    assert c.lines[0].line_discount == Decimal("10000.00")
    assert c.subtotal - c.discount_total == c.total
    assert sum(ln.invoice_discount_share for ln in c.lines) == c.discount_total - sum(ln.line_discount for ln in c.lines)
    assert all(ln.net_total >= 0 for ln in c.lines) and sum(ln.net_total for ln in c.lines) == c.total
    # qoldiq yaxlitlash: 3 teng qator, 100 so'm chegirma -> yig'indi aynan 100
    thirds = compute([LineInput(_svc(10)) for _ in range(3)], None, Decimal("0.10"))
    assert sum(ln.invoice_discount_share for ln in thirds.lines) == Decimal("0.10") and thirds.total == Decimal("29.90")
    full = compute([LineInput(_svc(10)), LineInput(_svc(20))], None, Decimal("30"))
    assert full.total == Decimal("0.00") and all(ln.vat_amount == 0 for ln in full.lines)


def _services(client, auth, n=2):
    admin = auth("admin")
    out = []
    for i in range(n):
        out.append(client.post("/services", headers=admin, json={
            "name": f"Xizmat {i}", "price": 100000 * (i + 1), "mxik": f"0930200100100000{i}", "package_code": "1500364",
            "vat_percent": 12}).json())
    return out


def _patient(client, auth, name="Hisob Bemor"):
    return client.post("/patients", json={**NEW, "name": name}, headers=auth("admin")).json()["id"]


def test_create_invoice_snapshot_totals_and_sellable_guard(client, auth):
    cashier, admin = auth("cashier"), auth("admin")
    s1, s2 = _services(client, auth)
    pid = _patient(client, auth)
    res = client.post("/invoices", headers=cashier, json={"patient_id": pid, "doctor": None, "lines": [
        {"service_id": s1["id"], "quantity": 2}, {"service_id": s2["id"]}]} | {"doctor_id": None})
    assert res.status_code == 201, res.text
    inv = res.json()
    assert inv["number"].startswith("INV-") and inv["status"] == "Draft" and inv["subtotal"] == 400000.0 and inv["total"] == 400000.0
    assert inv["vat_total"] == pytest.approx(400000 * 12 / 112, abs=0.01)
    assert [(ln["name"], ln["mxik"], ln["quantity"], ln["unit_price"]) for ln in inv["lines"]] == [
        ("Xizmat 0", "09302001001000000", 2, 100000.0), ("Xizmat 1", "09302001001000001", 1, 200000.0)]
    # narxnoma keyin o'zgarsa, hisob-faktura o'zgarmaydi
    client.put(f"/services/{s1['id']}", headers=admin, json={"price": 999999})
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["total"] == 400000.0
    # sotib bo'lmaydigan xizmat
    bare = client.post("/services", headers=admin, json={"name": "Kodsiz", "price": 1000}).json()
    bad = client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": bare["id"]}]})
    assert bad.status_code == 422 and "mxik" in bad.text and "Kodsiz" in bad.text
    client.put(f"/services/{s2['id']}", headers=admin, json={"is_active": False})
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": s2["id"]}]}).status_code == 422
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [
        {"service_id": "00000000-0000-0000-0000-000000000000"}]}).status_code == 422
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": []}).status_code == 422
    # raqamlar noyob va ketma-ket
    a = client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": s1["id"]}]}).json()["number"]
    b = client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": s1["id"]}]}).json()["number"]
    assert a != b and int(b[4:]) == int(a[4:]) + 1


def test_discount_needs_permission_and_reason_and_is_audited(client, auth):
    s1, _ = _services(client, auth)
    pid = _patient(client, auth)
    lines = [{"service_id": s1["id"], "quantity": 2}]
    receptionist_denied = client.post("/invoices", headers=auth("doctor"), json={"patient_id": pid, "lines": lines})
    assert receptionist_denied.status_code == 403                                               # finance:write yo'q
    body = {"patient_id": pid, "lines": lines, "discount_percent": 10}
    assert client.post("/invoices", headers=auth("cashier"), json=body).status_code == 422       # sabab yo'q
    ok = client.post("/invoices", headers=auth("cashier"), json={**body, "discount_reason": "Doimiy mijoz"})
    assert ok.status_code == 201 and ok.json()["total"] == 180000.0 and ok.json()["discount_total"] == 20000.0
    assert ok.json()["lines"][0]["invoice_discount_share"] == 20000.0
    # ruxsatsiz (finance:write bor, finance:discount yo'q): admin'dan ruxsatni olib tashlaymiz
    roles = {r["code"]: r for r in client.get("/roles", headers=auth("admin")).json()}
    cashier_perms = [p for p in roles["cashier"]["permissions"] if p != "finance:discount"]
    client.put(f"/roles/{roles['cashier']['id']}", headers=auth("admin"), json={"permissions": cashier_perms})
    assert client.post("/invoices", headers=auth("cashier"), json={**body, "discount_reason": "x sabab"}).status_code == 403
    assert client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": lines}).status_code == 201   # chegirmasiz mumkin
    audit = client.get("/security/audit", params={"entity_type": "invoice", "limit": 20}, headers=auth("admin")).json()["items"]
    created = [e for e in audit if e["action"] == "create"]
    assert any(e["details"].get("discount") == "20000.00" for e in created)


def test_discount_validation(client, auth):
    s1, _ = _services(client, auth)
    pid = _patient(client, auth)
    base = {"patient_id": pid, "discount_reason": "Sabab bor"}
    cashier = auth("cashier")
    both = client.post("/invoices", headers=cashier, json={**base, "lines": [{"service_id": s1["id"]}], "discount_percent": 5, "discount_amount": 100})
    assert both.status_code == 422
    too_big = client.post("/invoices", headers=cashier, json={**base, "lines": [{"service_id": s1["id"]}], "discount_amount": 100001})
    assert too_big.status_code == 422
    line_big = client.post("/invoices", headers=cashier, json={**base, "lines": [{"service_id": s1["id"], "discount_amount": 100001}]})
    assert line_big.status_code == 422
    assert client.post("/invoices", headers=cashier, json={**base, "lines": [{"service_id": s1["id"]}], "discount_percent": 101}).status_code == 422
    free = client.post("/invoices", headers=cashier, json={**base, "lines": [{"service_id": s1["id"]}], "discount_percent": 100}).json()
    assert free["total"] == 0.0 and free["vat_total"] == 0.0


def test_draft_edit_issue_cancel_lifecycle(client, auth):
    cashier = auth("cashier")
    s1, s2 = _services(client, auth)
    pid = _patient(client, auth)
    inv = client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": s1["id"]}]}).json()
    edited = client.put(f"/invoices/{inv['id']}", headers=cashier, json={"lines": [{"service_id": s2["id"], "quantity": 3}], "notes": "Tahrir"}).json()
    assert edited["total"] == 600000.0 and edited["notes"] == "Tahrir" and len(edited["lines"]) == 1 and edited["number"] == inv["number"]
    issued = client.post(f"/invoices/{inv['id']}/issue", headers=cashier).json()
    assert issued["status"] == "Issued" and issued["issued_at"]
    assert client.put(f"/invoices/{inv['id']}", headers=cashier, json={"lines": [{"service_id": s1["id"]}]}).status_code == 409   # qotgan
    assert client.post(f"/invoices/{inv['id']}/issue", headers=cashier).status_code == 409
    assert client.post(f"/invoices/{inv['id']}/cancel", headers=cashier, json={"reason": "x"}).status_code == 422                  # sabab qisqa
    cancelled = client.post(f"/invoices/{inv['id']}/cancel", headers=cashier, json={"reason": "Xato yaratilgan"}).json()
    assert cancelled["status"] == "Cancelled" and cancelled["cancel_reason"] == "Xato yaratilgan"
    assert client.post(f"/invoices/{inv['id']}/cancel", headers=cashier, json={"reason": "Yana"}).status_code == 409
    listed = client.get("/invoices", params={"status": "Cancelled"}, headers=cashier).json()
    assert [i["id"] for i in listed] == [inv["id"]]
    assert client.get("/invoices", params={"number": inv["number"]}, headers=cashier).json()[0]["id"] == inv["id"]
    assert client.get(f"/invoices/{inv['id']}", headers=auth("nurse")).status_code == 403


def test_appointment_link_default_doctor_and_duplicates(client, auth):
    cashier, admin = auth("cashier"), auth("admin")
    s1, _ = _services(client, auth)
    pid, other = _patient(client, auth), _patient(client, auth, "Boshqa")
    appt = client.post("/appointments", headers=admin, json={"patient_id": pid, "doctor": DOC, "date": "2026-12-01", "time": "10:00",
                                                            "type": "Konsultatsiya"}).json()
    inv = client.post("/invoices", headers=cashier, json={"patient_id": pid, "appointment_id": appt["id"], "lines": [{"service_id": s1["id"]}]})
    assert inv.status_code == 201 and inv.json()["doctor"] == DOC and inv.json()["lines"][0]["doctor"] == DOC     # ijrochi: qabul shifokori
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "appointment_id": appt["id"],
                                                           "lines": [{"service_id": s1["id"]}]}).status_code == 409
    assert client.post("/invoices", headers=cashier, json={"patient_id": other, "appointment_id": appt["id"],
                                                           "lines": [{"service_id": s1["id"]}]}).status_code == 422
    client.post(f"/invoices/{inv.json()['id']}/cancel", headers=cashier, json={"reason": "Qayta yaratish"})
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "appointment_id": appt["id"],
                                                           "lines": [{"service_id": s1["id"]}]}).status_code == 201      # bekor qilingandan keyin mumkin
