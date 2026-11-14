"""Tahliliy hisobotlar (v1.9.23): daromad, bemor oqimi, shifokor yuklamasi, kelmay qolish; JSON, Excel, PDF; davr va filial."""
import io
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
DOC = "Dr. Behruz Rustamov"
SERVICE = {"name": "Hisobot xizmati", "price": 112000, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 12}


def _sec(report, title_part):
    return next(s for s in report["sections"] if title_part in s["title"])


def _rep(client, h, kind, **params):
    res = client.get(f"/reports/analytics/{kind}", params=params, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def test_kinds_permissions_and_validation(client, auth):
    admin = auth("admin")
    assert {k["kind"] for k in client.get("/reports/analytics", headers=admin).json()} == {"revenue", "patient_flow", "doctor_load", "no_show"}
    assert client.get("/reports/analytics/revenue", headers=auth("nurse")).status_code == 403                       # reports:read yo'q
    assert client.get("/reports/analytics/unknown", headers=admin).status_code == 404
    assert client.get("/reports/analytics/revenue", params={"format": "docx"}, headers=admin).status_code == 422
    assert client.get("/reports/analytics/revenue", params={"date_from": "2026-03-01", "date_to": "2026-01-01"}, headers=admin).status_code == 422
    assert client.get("/reports/analytics/revenue", params={"all_branches": True}, headers=auth("doctor")).status_code == 403
    assert client.get("/reports/analytics/revenue", params={"all_branches": True}, headers=admin).status_code == 200


def test_revenue_json_xlsx_pdf_and_branch_scope(client, auth):
    admin, cashier = auth("admin"), auth("cashier")
    svc = client.post("/services", headers=admin, json=SERVICE).json()
    pid = client.post("/patients", json={**NEW, "name": "Hisobot Bemor"}, headers=admin).json()["id"]
    inv = client.post("/invoices", headers=cashier, json={"patient_id": pid, "issue": True, "lines": [{"service_id": svc["id"], "quantity": 3}]}).json()
    client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"})
    rep = _rep(client, admin, "revenue")
    assert rep["title"] == "Daromad hisoboti" and rep["to"] == date.today().isoformat() and rep["scope"]
    today = next(r for r in _sec(rep, "Kunlar")["rows"] if r[0] == date.today().isoformat())
    assert today[1] >= 1 and today[2] >= 336000 and today[4] == today[2] - today[3]
    methods = {r[0]: r for r in _sec(rep, "usuli")["rows"]}
    assert methods["Cash"][2] >= 336000 and _sec(rep, "usuli")["totals"][0] == "Jami"
    services = {r[0]: r for r in _sec(rep, "Xizmatlar")["rows"]}
    assert services["Hisobot xizmati"][1:3] == [3, 336000] and round(services["Hisobot xizmati"][3], 2) == round(336000 * 12 / 112, 2)
    wb = load_workbook(io.BytesIO(client.get("/reports/analytics/revenue", params={"format": "xlsx"}, headers=admin).content))
    assert wb.sheetnames[0] == "Hisobot" and any(n.startswith("To'lov usuli") for n in wb.sheetnames) and wb["Hisobot"]["A1"].value == "Daromad hisoboti"
    pdf = client.get("/reports/analytics/revenue", params={"format": "pdf"}, headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Daromad hisoboti" in text and "Hisobot xizmati" in text
    other = client.post("/branches", json={"name": "Hisobot filiali"}, headers=admin).json()["id"]
    empty = _rep(client, {**admin, "X-Branch-Id": other}, "revenue")
    assert all(s["rows"] == [] for s in empty["sections"]) and empty["scope"] == "Hisobot filiali"
    allb = _rep(client, {**admin, "X-Branch-Id": other}, "revenue", all_branches=True)
    assert allb["scope"] == "Hamma filial" and _sec(allb, "usuli")["rows"] == _sec(rep, "usuli")["rows"]
    far = _rep(client, admin, "revenue", date_from="2020-01-01", date_to="2020-01-31")
    assert all(s["rows"] == [] for s in far["sections"])
    with SessionLocal() as db:
        kinds = {(r.details["analytics"], r.details["format"]) for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "report")) if r.details.get("analytics")}
        assert kinds >= {("revenue", "xlsx"), ("revenue", "pdf")}


def test_patient_flow_counts_new_patients_visits_and_sources(client, auth):
    admin = auth("admin")
    client.post("/patients", json={**NEW, "name": "Oqim Bemor 1", "source": "instagram"}, headers=admin)
    pid = client.post("/patients", json={**NEW, "name": "Oqim Bemor 2", "source": "tavsiya"}, headers=admin).json()["id"]
    appt = client.post("/appointments", headers=admin, json={"patient_id": pid, "doctor": DOC, "date": date.today().isoformat(), "time": "20:30",
                                                             "type": "Konsultatsiya", "override_reason": "oqim testi"}).json()
    client.patch(f"/appointments/{appt['id']}/status", params={"status": "Completed"}, headers=admin)
    rep = _rep(client, admin, "patient_flow", date_from=date.today().isoformat(), date_to=date.today().isoformat())
    row = _sec(rep, "Kunlar")["rows"][0]
    assert row[0] == date.today().isoformat() and row[1] >= 2 and row[2] >= 1 and row[3] >= 1
    src = {r[0]: r[1] for r in _sec(rep, "manbasi")["rows"]}
    assert src["instagram"] >= 1 and src["tavsiya"] >= 1


def test_doctor_load_and_no_show_numbers(client, auth):
    admin = auth("admin")
    mon = date.today() + timedelta(days=(0 - date.today().weekday()) % 7 + 7)       # kelgusi dushanba (shifokor jadvalida)
    ids = []
    for i, status in enumerate(["Completed", "Completed", "No Show", "Cancelled"]):
        pid = client.post("/patients", json={**NEW, "name": f"Yuklama {i}"}, headers=admin).json()["id"]
        a = client.post("/appointments", headers=admin, json={"patient_id": pid, "doctor": DOC, "date": mon.isoformat(), "time": f"{9 + i}:00".zfill(5),
                                                              "type": "Konsultatsiya"})
        assert a.status_code == 201, a.text
        ids.append((a.json()["id"], status))
    for aid, status in ids:
        client.patch(f"/appointments/{aid}/status", params={"status": status}, headers=admin)
    rep = _rep(client, admin, "doctor_load", date_from=mon.isoformat(), date_to=mon.isoformat())
    row = next(r for r in _sec(rep, "Shifokorlar")["rows"] if r[0] == DOC)
    assert row[2:7] == [4, 2, 0, 1, 1] and row[7] == 33.3                              # jami, yakunlangan, rejalashtirilgan, kelmagan, bekor; 1/(2+1)
    assert row[9] == 7.0 and row[8] == 1.0 and row[10] == 14.3                          # jadval 09-17, tanaffus 13-14: 7 soat; band: 2 yakunlangan x 30 daq = 1 soat
    ns = _rep(client, admin, "no_show", date_from=mon.isoformat(), date_to=mon.isoformat())
    wk = _sec(ns, "Haftalar")["rows"][0]
    assert wk[0] == (mon - timedelta(days=mon.weekday())).isoformat() and wk[1:3] == [3, 1] and wk[3] == 33.3                # 3 qabul (yakun.+kelmagan), 1 kelmagan
    groups = {r[0]: r for r in _sec(ns, "Eslatma")["rows"]}
    assert groups["Eslatma yuborilmagan"][1:3] == [3, 1] and groups["Eslatma yuborilgan"][1:3] == [0, 0] and groups["Eslatma yuborilgan"][3] is None
    assert [r for r in _sec(ns, "Shifokorlar")["rows"] if r[0] == DOC][0][1:4] == [3, 1, 33.3]
    wb = load_workbook(io.BytesIO(client.get("/reports/analytics/doctor_load", params={"format": "xlsx", "date_from": mon.isoformat(), "date_to": mon.isoformat()},
                                              headers=admin).content))
    assert wb["Shifokorlar bo'yicha"]["A2"].value is not None
