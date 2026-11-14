"""Buxgalteriya (1C) eksporti (v1.9.22): to'plamlar, Excel/CSV, davr va filial filtri, Sozlamalarda ustun xaritasi va format."""
import csv
import io
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
SERVICE = {"name": "Eksport xizmati", "price": 112000, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 12}


def _paid_invoice(client, auth, patient_name="Eksport Bemor", qty=2):
    admin = auth("admin")
    svc = client.post("/services", headers=admin, json=SERVICE).json()
    pid = client.post("/patients", json={**NEW, "name": patient_name}, headers=admin).json()["id"]
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "issue": True, "lines": [{"service_id": svc["id"], "quantity": qty}]}).json()
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"}).json()
    return inv, pay


def _xlsx(res):
    assert res.status_code == 200, res.text
    wb = load_workbook(io.BytesIO(res.content))
    return wb


def _csv(res):
    assert res.status_code == 200, res.text
    assert res.content.startswith(b"\xef\xbb\xbf")                                           # UTF-8 BOM (Excel/1C)
    return res.content.decode("utf-8-sig")


def test_datasets_defaults_and_permissions(client, auth):
    admin = auth("admin")
    ds = {d["name"]: d for d in client.get("/settings/exports", headers=admin).json()}
    assert set(ds) == {"sales", "payments", "cash_shifts", "stock_movements", "commissions"} and ds["sales"]["customized"] is False
    assert [c["header"] for c in ds["sales"]["columns"][:3]] == ["Sana", "Hisob-faktura", "Bemor"] and all(c["enabled"] for c in ds["sales"]["columns"])
    assert client.get("/exports/sales", headers=auth("cashier")).status_code == 403                    # exports:read faqat administrator
    assert client.get("/exports/sales", headers=auth("doctor")).status_code == 403
    assert client.get("/exports/unknown", headers=admin).status_code == 404
    assert client.get("/exports/sales", params={"date_from": "2026-02-01", "date_to": "2026-01-01"}, headers=admin).status_code == 422
    assert client.get("/exports/sales", params={"date_from": "2024-01-01", "date_to": "2026-01-01"}, headers=admin).status_code == 422    # davr > 400 kun
    assert client.get("/exports/sales", params={"format": "pdf"}, headers=admin).status_code == 422


def test_sales_and_payments_xlsx_with_summary_sheets_and_branch_filter(client, auth):
    admin = auth("admin")
    inv, pay = _paid_invoice(client, auth)
    wb = _xlsx(client.get("/exports/sales", headers=admin))
    ws = wb["Sotuvlar (xizmat bo'yicha)"]
    header = [c.value for c in ws[1]]
    assert header[:5] == ["Sana", "Hisob-faktura", "Bemor", "Xizmat", "MXIK"] and ws.freeze_panes == "A2"
    row = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[1] == inv["number"])
    cols = dict(zip(header, row, strict=True))
    assert cols["Bemor"] == "Eksport Bemor" and cols["Xizmat"] == "Eksport xizmati" and cols["Soni"] == 2 and cols["Summa"] == 224000
    assert cols["QQS summasi"] == round(224000 * 12 / 112, 2) and isinstance(cols["Summa"], (int, float)) and isinstance(cols["Sana"], (date,)) or hasattr(cols["Sana"], "year")
    summary = wb["Xizmat bo'yicha jami"]
    assert any(r[0] == "Eksport xizmati" and r[1] == 2 and r[2] == 224000 for r in summary.iter_rows(min_row=2, values_only=True))
    pw = _xlsx(client.get("/exports/payments", headers=admin))
    prow = [dict(zip([c.value for c in pw["To'lovlar (usul bo'yicha)"][1]], r, strict=True)) for r in pw["To'lovlar (usul bo'yicha)"].iter_rows(min_row=2, values_only=True)]
    mine = next(r for r in prow if r["Hisob-faktura"] == inv["number"])
    assert mine["Usul"] == "Cash" and mine["Summa"] == 224000 and mine["Sof"] == 224000 and mine["Fiskal chek"].startswith("MOCK-") and mine["Smena (Z)"] is None
    by_method = {r[0]: r for r in pw["Usul bo'yicha jami"].iter_rows(min_row=2, values_only=True)}
    assert by_method["Cash"][2] >= 224000 and by_method["Cash"][1] >= 1
    other = client.post("/branches", json={"name": "Eksport filiali"}, headers=admin).json()["id"]
    empty = _xlsx(client.get("/exports/sales", headers={**admin, "X-Branch-Id": other}))
    assert empty["Sotuvlar (xizmat bo'yicha)"].max_row == 1                                              # faqat sarlavha
    allb = _xlsx(client.get("/exports/sales", params={"all_branches": True}, headers={**admin, "X-Branch-Id": other}))
    assert allb["Sotuvlar (xizmat bo'yicha)"].max_row == wb["Sotuvlar (xizmat bo'yicha)"].max_row
    far = _xlsx(client.get("/exports/sales", params={"date_from": "2020-01-01", "date_to": "2020-02-01"}, headers=admin))
    assert far["Sotuvlar (xizmat bo'yicha)"].max_row == 1                                                # davr filtri


def test_csv_format_and_column_map_are_editable(client, auth):
    admin = auth("admin")
    inv, _ = _paid_invoice(client, auth, "=Formula Bemor", 1)
    text = _csv(client.get("/exports/sales", params={"format": "csv"}, headers=admin))
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    head = rows[0]
    mine = dict(zip(head, next(r for r in rows[1:] if r[1] == inv["number"]), strict=False))
    assert mine["Summa"] == "112000.00" and mine["Bemor"] == "'=Formula Bemor" and mine["Sana"] == date.today().isoformat()      # nuqta, ISO, formula himoyasi
    # format: 1C ruscha (sana kun.oy.yil, o'nlik vergul, ; ajratgich)
    assert client.put("/settings/export-format", json={"date_format": "dmy", "decimal_separator": ",", "csv_delimiter": ";"}, headers=admin).status_code == 200
    assert client.put("/settings/export-format", json={"date_format": "iso", "decimal_separator": ",", "csv_delimiter": ","}, headers=admin).status_code == 422
    assert client.put("/settings/export-format", json={"date_format": "x", "decimal_separator": ",", "csv_delimiter": ";"}, headers=admin).status_code == 422
    ru_rows = list(csv.reader(io.StringIO(_csv(client.get("/exports/sales", params={"format": "csv"}, headers=admin))), delimiter=";"))
    ru = dict(zip(head, next(r for r in ru_rows if r[1] == inv["number"]), strict=True))
    assert ru["Summa"] == "112000,00" and ru["Sana"] == date.today().strftime("%d.%m.%Y")
    assert client.get("/settings/export-format", headers=admin).json() == {"date_format": "dmy", "decimal_separator": ",", "csv_delimiter": ";"}
    # ustun xaritasi: qayta nomlash, tartib, o'chirish
    cols = [{"key": "number", "header": "Nomer dokumenta", "enabled": True}, {"key": "date", "header": "Data", "enabled": True},
            {"key": "total", "header": "Summa s NDS", "enabled": True}, {"key": "patient", "header": "Kontragent", "enabled": True},
            {"key": "mxik", "header": "MXIK", "enabled": False}]
    put = client.put("/settings/exports/sales", json={"columns": cols}, headers=admin)
    assert put.status_code == 200 and put.json()["customized"] is True
    got = put.json()["columns"]
    assert [c["header"] for c in got if c["enabled"]] == ["Nomer dokumenta", "Data", "Summa s NDS", "Kontragent"] and got[-1]["enabled"] is False     # qolganlari o'chiq
    mapped = list(csv.reader(io.StringIO(_csv(client.get("/exports/sales", params={"format": "csv"}, headers=admin))), delimiter=";"))
    assert mapped[0] == ["Nomer dokumenta", "Data", "Summa s NDS", "Kontragent"]
    assert next(r for r in mapped[1:] if r[0] == inv["number"])[2] == "112000,00"
    wb = _xlsx(client.get("/exports/sales", headers=admin))
    assert [c.value for c in wb["Sotuvlar (xizmat bo'yicha)"][1]] == ["Nomer dokumenta", "Data", "Summa s NDS", "Kontragent"]
    # tekshiruvlar
    assert client.put("/settings/exports/sales", json={"columns": [{"key": "nope", "header": "X"}]}, headers=admin).status_code == 422
    assert client.put("/settings/exports/sales", json={"columns": [{"key": "date", "header": "A"}, {"key": "number", "header": "a"}]}, headers=admin).status_code == 422
    assert client.put("/settings/exports/sales", json={"columns": [{"key": "date", "header": "A", "enabled": False}]}, headers=admin).status_code == 422
    assert client.put("/settings/exports/sales", json={"columns": [{"key": "date", "header": "A"}, {"key": "date", "header": "B"}]}, headers=admin).status_code == 422
    assert client.put("/settings/exports/sales", json={"columns": cols}, headers=auth("nurse")).status_code == 403
    reset = client.delete("/settings/exports/sales", headers=admin)
    assert reset.json()["customized"] is False and reset.json()["columns"][0]["header"] == "Sana"


def test_other_datasets_and_audit(client, auth):
    admin = auth("admin")
    _paid_invoice(client, auth)
    client.post("/warehouse/items", json={"name": "Eksport materiali", "unit": "dona"}, headers=admin)
    item = client.get("/warehouse/items", headers=admin).json()[0]["id"]
    client.post("/warehouse/receipts", headers=admin, json={"lines": [{"item_id": item, "batch_no": "E-1", "qty": 5, "unit_cost": 200,
                                                                      "expires_on": (date.today() + timedelta(days=90)).isoformat()}]})
    mv = _xlsx(client.get("/exports/stock_movements", headers=admin))["Ombor harakatlari"]
    h = [c.value for c in mv[1]]
    row = next(dict(zip(h, r, strict=True)) for r in mv.iter_rows(min_row=2, values_only=True) if r[h.index("Partiya")] == "E-1")
    assert row["Tur"] == "Receipt" and row["Miqdor"] == 5 and row["Summa"] == 1000 and row["Material"] == "Eksport materiali"
    sh = _xlsx(client.get("/exports/cash_shifts", headers=admin))["Kassa smenalari"]
    assert sh.max_row >= 2 and [c.value for c in sh[1]][:2] == ["Z-raqam", "Kassir"]
    cm = _xlsx(client.get("/exports/commissions", params={"date_from": (date.today() - timedelta(days=300)).isoformat()}, headers=admin))["Shifokor foizlari"]
    assert [c.value for c in cm[1]][:3] == ["Sana", "Shifokor", "Tur"]
    with SessionLocal() as db:
        logged = db.scalars(select(AuditLog).where(AuditLog.entity_type == "export")).all()
        assert {r.details["dataset"] for r in logged} >= {"stock_movements", "cash_shifts", "commissions"} and all(r.details["format"] == "xlsx" for r in logged)
