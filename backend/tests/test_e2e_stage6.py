"""6-bosqich "Shart"i: hisobotlar (daromad, oqim, yuklama, kelmay qolish), 1C eksporti, sug'urta bo'linishi/qarzi/reyestri va AI xulosa
bitta zanjirda: hammasi bazadagi haqiqiy hisob-fakturadan, tasdiqlanmagan AI matni yozuvga kirmaydi.

Zanjir: sug'urtali hisob-faktura (70% qoplanadi) -> bemor ulushi kassada to'lanadi -> daromad hisoboti va 1C eksportida ko'rinadi ->
kompaniya qarzi va oylik reyestr -> kompaniya to'lovi qarzni yopadi -> ko'rik uchun AI qoralama shifokor tasdiqlagach yozuvga kiradi."""
import io
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook

from app.core.config import settings
from app.services import llm
from tests.test_ai_summary import _enable, _Resp
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
D = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731
DOC = "Dr. Behruz Rustamov"


def _rev_today(client, admin):
    rep = client.get("/reports/analytics/revenue", headers=admin).json()
    sec = next(s for s in rep["sections"] if "Kunlar" in s["title"])
    row = next((r for r in sec["rows"] if r[0] == date.today().isoformat()), None)
    return row[2] if row else 0


def test_stage6_reports_export_insurance_and_ai_chain(client, auth, monkeypatch):
    admin, cashier, doctor = auth("admin"), auth("cashier"), auth("doctor")
    before = _rev_today(client, admin)
    # 1. sug'urta modeli: kompaniya -> shartnoma (70%) -> polis
    ins = client.post("/insurance/insurers", json={"name": "Shart Sug'urta", "tin": "300555666", "payment_days": 30}, headers=admin).json()
    svc = client.post("/services", headers=admin, json={"name": "Shart xizmati", "price": 100000, "mxik": "09302001001000000", "package_code": "1500364",
                                                       "vat_percent": 12}).json()["id"]
    contract = client.post("/insurance/contracts", headers=admin, json={"insurer_id": ins["id"], "number": "SH-1", "valid_from": D(-30), "valid_to": D(300),
                                                                         "services": [{"service_id": svc, "coverage_percent": 70}]}).json()
    pid = client.post("/patients", json={**NEW, "name": "Shart Bemor"}, headers=admin).json()["id"]
    pol = client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": contract["id"], "number": "SP-1", "valid_from": D(-20)}).json()
    # 2. hisob-faktura bemor va sug'urta ulushiga bo'linadi; bemor ulushi kassada to'lanadi
    inv = client.post("/invoices", headers=cashier, json={"patient_id": pid, "policy_id": pol["id"], "issue": True, "lines": [{"service_id": svc, "quantity": 2}]}).json()
    assert inv["insurer_total"] == 140000, inv
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"})
    assert pay.status_code in (200, 201), pay.text
    # 3. hisobot: daromadga faqat bemor ulushi tushadi
    assert _rev_today(client, admin) - before == 60000
    for kind in ("revenue", "patient_flow", "doctor_load", "no_show"):
        assert client.get(f"/reports/analytics/{kind}", headers=admin).status_code == 200
        for fmt, magic in (("xlsx", b"PK"), ("pdf", b"%PDF")):
            res = client.get(f"/reports/analytics/{kind}", params={"format": fmt}, headers=admin)
            assert res.status_code == 200 and res.content.startswith(magic), (kind, fmt)
    # 4. 1C eksporti: sotuv qatori va to'lov, chek ID bilan
    sales = load_workbook(io.BytesIO(client.get("/exports/sales", headers=admin).content))["Sotuvlar (xizmat bo'yicha)"]
    header = [c.value for c in sales[1]]
    mine = [dict(zip(header, r, strict=True)) for r in sales.iter_rows(min_row=2, values_only=True) if r[1] == inv["number"]]
    assert len(mine) == 1 and mine[0]["Xizmat"] == "Shart xizmati" and mine[0]["Soni"] == 2
    csv = client.get("/exports/payments", params={"format": "csv"}, headers=admin)
    assert csv.status_code == 200 and inv["number"] in csv.content.decode("utf-8-sig") and "MOCK-" in csv.content.decode("utf-8-sig")
    # 5. kompaniya qarzi va oylik reyestr
    debt = client.get(f"/insurance/debts/{ins['id']}", headers=admin).json()
    assert (debt["charged"], debt["paid"], debt["balance"]) == (140000, 0, 140000)
    month = date.today().strftime("%Y-%m")
    reg = client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month}, headers=admin).json()
    assert reg["header"]["insurer_total"] == 140000 and reg["header"]["patient_total"] == 60000 and reg["rows"][0]["invoice"] == inv["number"]
    wb = load_workbook(io.BytesIO(client.get("/insurance/registry", params={"insurer_id": ins["id"], "month": month, "format": "xlsx"}, headers=admin).content))
    assert wb.sheetnames == ["Reyestr", "Xizmatlar bo'yicha"]
    # 6. kompaniya to'lovi qarzni yopadi
    assert client.post("/insurance/payments", headers=admin, json={"insurer_id": ins["id"], "amount": 140000, "reference": "SH-PP-1"}).status_code == 201
    closed = client.get(f"/insurance/debts/{ins['id']}", headers=admin).json()
    assert closed["balance"] == 0 and closed["open_invoices"] == []
    # 7. AI: AI_ENABLED=false da demo (tasdiqlanmaydi), lokal LLM bilan qoralama faqat shifokor tasdiqlagach yozuvga kiradi
    enc = client.post("/emr", headers=doctor, json={"patient_id": pid, "doctor": DOC, "diagnosis": "Gripp", "complaints": "Isitma", "anamnesis": "2 kun",
                                                    "examination": "T 38.5", "recommendations": "Ko'p suyuqlik", "prescription": "Paratsetamol 500 mg",
                                                    "visit_date": date.today().isoformat()}).json()["id"]
    assert settings.ai_enabled is False
    demo = client.post(f"/emr/{enc}/ai-summary", headers=doctor)
    assert demo.status_code == 201 and demo.json()["draft"]["demo"] is True
    assert client.post(f"/emr/{enc}/ai-summary/{demo.json()['draft']['id']}/approve", headers=doctor).status_code == 409
    _enable(monkeypatch)
    monkeypatch.setattr(llm.httpx, "post", lambda url, headers, json, timeout: _Resp())
    draft = client.post(f"/emr/{enc}/ai-summary", headers=doctor).json()["draft"]
    assert draft["status"] == "Draft" and client.get(f"/emr/{enc}/ai-summary", headers=doctor).json()["approved"] is None
    assert client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=admin).status_code == 403       # ko'rik shifokori emas
    ok = client.post(f"/emr/{enc}/ai-summary/{draft['id']}/approve", headers=doctor)
    assert ok.status_code == 200 and ok.json()["approved"]["status"] == "Approved"
