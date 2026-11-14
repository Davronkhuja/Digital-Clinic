"""Kompaniya to'lovlari, qarzdorlik (FIFO, muddat kesimi) va oylik reyestr Excel (v1.9.27)."""
import io
from datetime import UTC, date, datetime, timedelta

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog, Invoice
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
D = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731
ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def world(client, auth):
    admin = auth("admin")
    ins = client.post("/insurance/insurers", json={"name": "Qarz Sug'urta", "tin": "300111222", "payment_days": 15}, headers=admin).json()
    svc = client.post("/services", headers=admin, json={"name": "Reyestr xizmati", "price": 100000, "mxik": "09302001001000000", "package_code": "1500364",
                                                       "vat_percent": 12}).json()["id"]
    contract = client.post("/insurance/contracts", headers=admin, json={"insurer_id": ins["id"], "number": "QS-1", "valid_from": D(-400), "valid_to": D(300),
                                                                         "services": [{"service_id": svc, "coverage_percent": 100}]}).json()
    pid = client.post("/patients", json={**NEW, "name": "Reyestr Bemor"}, headers=admin).json()["id"]
    pol = client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": contract["id"], "number": "QP-1", "valid_from": D(-300)}).json()
    return admin, ins, svc, pid, pol


def _inv(client, auth, svc, pid, pol, qty, days_ago):
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "policy_id": pol["id"], "issue": True, "lines": [{"service_id": svc, "quantity": qty}]}).json()
    assert inv["insurer_total"] == 100000 * qty, inv
    with SessionLocal() as db:                                                         # hisob-faktura sanasini orqaga suramiz
        row = db.get(Invoice, inv["id"])
        row.issued_at = datetime.now(UTC) - timedelta(days=days_ago)
        db.commit()
    return inv


def test_payments_fifo_debt_aging_and_reversal(client, auth, world):
    admin, ins, svc, pid, pol = world
    i1, i2, i3 = _inv(client, auth, svc, pid, pol, 1, 120), _inv(client, auth, svc, pid, pol, 2, 45), _inv(client, auth, svc, pid, pol, 1, 0)
    assert client.get("/insurance/debts", headers=auth("cashier")).status_code == 200                      # insurance:read
    d0 = client.get(f"/insurance/debts/{ins['id']}", headers=admin).json()
    assert (d0["charged"], d0["paid"], d0["balance"], d0["overpaid"]) == (400000, 0, 400000, 0) and len(d0["open_invoices"]) == 3
    assert round(sum(d0["aging"].values()), 2) == 400000 and d0["aging"]["current"] >= 100000                 # bugungi hisob-faktura muddati o'tmagan
    pay = client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 150000, "reference": "PP-77", "paid_on": D(0)})
    assert pay.status_code == 201, pay.text
    d1 = client.get(f"/insurance/debts/{ins['id']}", headers=admin).json()
    assert (d1["charged"], d1["paid"], d1["balance"]) == (400000, 150000, 250000)
    open_by = {r["number"]: r for r in d1["open_invoices"]}
    assert i1["number"] not in open_by                                                                       # eng eskisi (FIFO) to'liq yopildi
    assert open_by[i2["number"]]["paid"] == 50000 and open_by[i2["number"]]["outstanding"] == 150000 and open_by[i3["number"]]["outstanding"] == 100000
    assert open_by[i2["number"]]["days_overdue"] >= 1 and open_by[i3["number"]]["days_overdue"] == 0 and open_by[i3["number"]]["due_date"] > D(0)
    assert round(sum(d1["aging"].values()), 2) == 250000 and d1["overdue"] == 150000 and d1["aging"]["current"] == 100000
    assert any(d["insurer"] == "Qarz Sug'urta" for d in client.get("/insurance/debts", headers=admin).json())
    # to'lov qiymati oshib ketsa: ortiqcha to'lov
    client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 300000})
    d2 = client.get(f"/insurance/debts/{ins['id']}", headers=admin).json()
    assert d2["balance"] == -50000 and d2["overpaid"] == 50000 and d2["open_invoices"] == [] and d2["overdue"] == 0
    # xato to'lovni bekor qilish: qarz qaytadi
    first = client.get("/insurance/payments", headers=admin).json()[-1]
    assert client.post(f"/insurance/payments/{first['id']}/reverse", json={"reason": "x"}, headers=admin).status_code == 422
    rev = client.post(f"/insurance/payments/{first['id']}/reverse", json={"reason": "noto'g'ri summa kiritildi"}, headers=admin)
    assert rev.status_code == 200 and rev.json()["reversed"] is True
    assert client.post(f"/insurance/payments/{first['id']}/reverse", json={"reason": "yana"}, headers=admin).status_code == 409
    d3 = client.get(f"/insurance/debts/{ins['id']}", headers=admin).json()
    assert d3["paid"] == 300000 and d3["balance"] == 100000
    plist = client.get("/insurance/payments", params={"insurer_id": ins["id"]}, headers=auth("cashier")).json()
    assert {p["amount"] for p in plist} == {300000, 150000} and sum(p["reversed"] for p in plist) == 1
    assert client.post(f"/insurance/payments/{ZERO}/reverse", json={"reason": "yo'q to'lov"}, headers=admin).status_code == 404


def test_payment_validation_and_permissions(client, auth, world):
    admin, ins, svc, pid, pol = world
    body = {"insurer_id": ins["id"], "amount": 1000}
    assert client.post("/insurance/payments", json={**body, "amount": 0}, headers=admin).status_code == 422
    assert client.post("/insurance/payments", json={**body, "amount": -5}, headers=admin).status_code == 422
    assert client.post("/insurance/payments", json={**body, "paid_on": D(3)}, headers=admin).status_code == 422                # kelajak sanasi
    assert client.post("/insurance/payments", json={"insurer_id": ZERO, "amount": 1000}, headers=admin).status_code == 422
    assert client.post("/insurance/payments", json=body, headers=auth("cashier")).status_code == 403                            # insurance:manage faqat admin
    assert client.post("/insurance/payments", json=body, headers=auth("receptionist")).status_code == 403
    assert client.get("/insurance/debts", headers=auth("doctor")).status_code == 403
    assert client.get(f"/insurance/debts/{ZERO}", headers=admin).status_code == 404
    assert client.get("/insurance/debts", headers=admin).json() == []                                                            # hali hisob-faktura va to'lov yo'q
    assert [d["insurer"] for d in client.get("/insurance/debts", params={"include_zero": True}, headers=admin).json()] == ["Qarz Sug'urta"]
    with SessionLocal() as db:
        assert db.scalars(select(AuditLog).where(AuditLog.entity_type == "insurer_payment")).all() == []


def test_monthly_registry_json_xlsx_filters_and_audit(client, auth, world):
    admin, ins, svc, pid, pol = world
    old, now = _inv(client, auth, svc, pid, pol, 1, 100), _inv(client, auth, svc, pid, pol, 3, 0)
    month = date.today().strftime("%Y-%m")
    rep = client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month}, headers=admin).json()
    h = rep["header"]
    assert h["insurer"] == "Qarz Sug'urta" and h["tin"] == "300111222" and h["month"] == month and h["invoices"] == 1 and h["lines"] == 1
    assert h["insurer_total"] == 300000 and h["patient_total"] == 0 and h["number"].startswith("REE-")
    row = rep["rows"][0]
    assert row["invoice"] == now["number"] and row["policy"] == "QP-1" and row["contract"] == "QS-1" and row["service"] == "Reyestr xizmati" and row["qty"] == 3
    assert (row["line_total"], row["insurer_amount"], row["patient_amount"]) == (300000, 300000, 0)
    old_month = (date.today() - timedelta(days=100)).strftime("%Y-%m")
    assert client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": old_month}, headers=admin).json()["rows"][0]["invoice"] == old["number"]
    wb = load_workbook(io.BytesIO(client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month, "format": "xlsx"}, headers=admin).content))
    assert wb.sheetnames == ["Reyestr", "Xizmatlar bo'yicha"]
    ws = wb["Reyestr"]
    assert ws["A1"].value.startswith("Xizmatlar reyestri") and "Qarz Sug'urta" in ws["A3"].value and "300111222" in ws["A3"].value
    assert [c.value for c in ws[6]][:3] == ["Sana", "Hisob-faktura", "Bemor"]
    data = [c.value for c in ws[7]]
    assert data[1] == now["number"] and data[2] == "Reyestr Bemor" and data[9] == 300000 and data[10] == 0
    total_row = next(r for r in ws.iter_rows(values_only=True) if r[0] == "Jami")
    assert total_row[9] == 300000 and total_row[7] == 3
    assert wb["Xizmatlar bo'yicha"]["A2"].value == "Reyestr xizmati" and wb["Xizmatlar bo'yicha"]["D2"].value == 300000
    other_ins = client.post("/insurance/insurers", json={"name": "Boshqa Reyestr"}, headers=admin).json()
    assert client.get("/insurance/registry", params={"insurer_id": other_ins["id"], "month": month}, headers=admin).json()["rows"] == []
    branch = client.post("/branches", json={"name": "Reyestr filiali"}, headers=admin).json()["id"]
    assert client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month}, headers={**admin, "X-Branch-Id": branch}).json()["rows"] == []
    allb = client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month, "all_branches": True}, headers={**admin, "X-Branch-Id": branch}).json()
    assert allb["header"]["insurer_total"] == 300000
    assert client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": "2026-13"}, headers=admin).status_code == 422
    assert client.get("/insurance/registry", params={"insurer_id": ZERO, "month": month}, headers=admin).status_code == 404
    assert client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month}, headers=auth("cashier")).status_code == 403
    with SessionLocal() as db:
        logged = db.scalars(select(AuditLog).where(AuditLog.entity_type == "insurance_registry")).all()
        assert len(logged) == 1 and logged[0].details["month"] == month and logged[0].details["total"] == "300000.00"
