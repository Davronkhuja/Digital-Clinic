"""5-bosqich "Shart"i: xizmat tannarxi sarf materiallar bilan avtomatik hisoblanadi.

Zanjir: material -> kirim (ikki partiya, muddat) -> xizmat sarf normasi -> tannarx avtomatik -> to'liq to'lov FEFO bo'yicha sarf yozadi ->
ombor va tannarx o'zgaradi -> 30 kunlik yaroqlilik ogohlantirishi -> filiallar orasida ko'chirish (partiya, muddat, narx saqlanadi) ->
ikkinchi filialda tannarx o'z ombor narxidan hisoblanadi -> jurnal yaxlitligi."""
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import StockBatch, StockMovement
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")


def _on(h, bid):
    return {**h, "X-Branch-Id": bid}


def _cost(client, h, sid):
    return client.get(f"/warehouse/services/{sid}/cost", headers=h).json()


def test_service_cost_follows_stock_consumption_and_branches(client, auth):
    admin, cashier = auth("admin"), auth("cashier")
    # 1. katalog va kirim: ikki partiya (arzon va muddati yaqin / qimmat va uzoq)
    syringe = client.post("/warehouse/items", json={"name": "Shprits 5 ml", "unit": "dona", "min_qty": 30}, headers=admin).json()["id"]
    gel = client.post("/warehouse/items", json={"name": "Gel", "unit": "litr"}, headers=admin).json()["id"]
    day = lambda n: (date.today() + timedelta(days=n)).isoformat()      # noqa: E731
    client.post("/warehouse/receipts", headers=admin, json={"supplier": "MedPlus", "lines": [
        {"item_id": syringe, "batch_no": "S-SOON", "qty": 20, "unit_cost": 400, "expires_on": day(20)},
        {"item_id": syringe, "batch_no": "S-LATE", "qty": 30, "unit_cost": 600, "expires_on": day(300)},
        {"item_id": gel, "batch_no": "G-1", "qty": 10, "unit_cost": 20000, "expires_on": day(200)}]})

    # 2. sarf normasi va avtomatik tannarx (o'rtacha tortilgan narx: (20*400 + 30*600) / 50 = 520)
    svc = client.post("/services", headers=admin, json={"name": "Inyeksiya", "price": 112000, "mxik": "09302001001000000",
                                                       "package_code": "1500364", "vat_percent": 12}).json()["id"]
    client.put(f"/warehouse/services/{svc}/materials", headers=admin, json={"materials": [{"item_id": syringe, "qty": 2}, {"item_id": gel, "qty": 0.05}]})
    c1 = _cost(client, admin, svc)
    assert c1["complete"] is True and c1["cost"] == 2 * 520 + 0.05 * 20000 == 2040
    assert c1["net_price"] == 100000 and c1["margin"] == 97960

    # 3. ogohlantirishlar: Shprits 50 >= 30 (kam emas), S-SOON 20 kunda tugaydi
    alerts = client.get("/warehouse/alerts", headers=admin).json()
    assert alerts["low_stock"] == [] and [b["batch_no"] for b in alerts["expiring"]] == ["S-SOON"] and alerts["expired"] == []

    # 4. to'liq to'lov: 10 ta inyeksiya = 20 shprits (FEFO: hammasi S-SOON), 0.5 litr gel
    pid = client.post("/patients", json={**NEW, "name": "Shart Bemor"}, headers=admin).json()["id"]
    inv = client.post("/invoices", headers=cashier, json={"patient_id": pid, "issue": True, "lines": [{"service_id": svc, "quantity": 10}]}).json()
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"})
    assert pay.status_code == 201 and pay.json()["receipt_status"] == "Issued"
    stock = {r["name"]: r for r in client.get("/warehouse/stock", headers=admin).json()}
    assert stock["Shprits 5 ml"]["qty"] == 30 and stock["Gel"]["qty"] == 9.5
    batches = {b["batch_no"]: b["qty_remaining"] for b in client.get("/warehouse/batches", headers=admin).json()}
    assert batches == {"S-LATE": 30, "G-1": 9.5}                                                  # S-SOON to'liq ishlatildi (FEFO)
    usage = client.get("/warehouse/movements", params={"kind": "Consumption"}, headers=admin).json()
    assert {m["item"]: m["qty"] for m in usage} == {"Shprits 5 ml": -20, "Gel": -0.5} and all(inv["number"] in m["reason"] for m in usage)

    # 5. qoldiq faqat qimmat partiyada: tannarx avtomatik oshdi (600 * 2 + 1000 = 2200)
    c2 = _cost(client, admin, svc)
    assert c2["cost"] == 2 * 600 + 0.05 * 20000 == 2200 and c2["cost"] > c1["cost"]
    client.post("/warehouse/receipts", headers=admin, json={"lines": [{"item_id": syringe, "batch_no": "S-NEW", "qty": 50, "unit_cost": 500, "expires_on": day(365)}]})
    assert _cost(client, admin, svc)["cost"] == 2 * 537.5 + 1000                                  # (30*600 + 50*500)/80 = 537.5

    # 6. filial: 20 ta shpritsni ikkinchi filialga ko'chirish (partiya raqami, muddat va narx saqlanadi)
    other = client.post("/branches", json={"name": "Shart filiali"}, headers=admin).json()["id"]
    t = client.post("/warehouse/transfers", headers=admin, json={"to_branch_id": other, "lines": [{"item_id": syringe, "qty": 20}]}).json()
    assert [(ln["batch_no"], ln["qty"], ln["unit_cost"]) for ln in t["lines"]] == [("S-LATE", 20, 600)]       # FEFO: muddati yaqini (S-LATE) avval
    assert client.post(f"/warehouse/transfers/{t['id']}/receive", headers=_on(admin, other)).status_code == 200
    there = client.get("/warehouse/batches", headers=_on(admin, other)).json()
    assert [(b["batch_no"], b["qty_remaining"], b["unit_cost"], b["expires_on"]) for b in there] == [("S-LATE", 20, 600, day(300))]
    c_other = _cost(client, _on(admin, other), svc)
    syr = next(m for m in c_other["materials"] if m["item"] == "Shprits 5 ml")
    gel_line = next(m for m in c_other["materials"] if m["item"] == "Gel")
    assert syr["unit_cost"] == 600 and syr["source"] == "stock" and gel_line["source"] == "unknown" and c_other["complete"] is False   # gel yo'q: narx noma'lum
    main_after = _cost(client, admin, svc)
    assert next(m for m in main_after["materials"] if m["item"] == "Shprits 5 ml")["unit_cost"] == round((10 * 600 + 50 * 500) / 60, 2)   # asosiy filial: 10 S-LATE + 50 S-NEW

    # 7. jurnal yaxlitligi: har partiya uchun harakatlar yig'indisi = qoldiq; ko'chirishda qiymat yo'qolmaydi
    with SessionLocal() as db:
        for b in db.scalars(select(StockBatch)):
            assert db.scalar(select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.batch_id == b.id)) == b.qty_remaining
        assert db.scalar(select(func.sum(StockBatch.qty_remaining)).where(StockBatch.item_id == syringe)) == 80
