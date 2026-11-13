"""Xizmat sarf normasi va avtomatik tannarx (v1.9.4)."""
from datetime import date, timedelta

SERVICE = {"name": "Inyeksiya", "price": 112000, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 12}


def _item(client, h, name, unit="dona"):
    return client.post("/warehouse/items", json={"name": name, "unit": unit}, headers=h).json()["id"]


def _receive(client, h, item, qty, cost, batch, days=200):
    body = {"lines": [{"item_id": item, "batch_no": batch, "qty": qty, "unit_cost": cost, "expires_on": (date.today() + timedelta(days=days)).isoformat()}]}
    assert client.post("/warehouse/receipts", json=body, headers=h).status_code == 201


def _service(client, h):
    return client.post("/services", json=SERVICE, headers=h).json()["id"]


def _cost(client, h, sid):
    return client.get(f"/warehouse/services/{sid}/cost", headers=h).json()


def test_cost_is_computed_from_norm_and_stock_prices_automatically(client, auth):
    h = auth("admin")
    sid = _service(client, h)
    syringe, gel = _item(client, h, "Shprits"), _item(client, h, "Gel", "litr")
    norms = client.put(f"/warehouse/services/{sid}/materials", headers=h, json={"materials": [
        {"item_id": syringe, "qty": 2}, {"item_id": gel, "qty": 0.05}]})
    assert norms.status_code == 200 and {n["item"]: n["qty"] for n in norms.json()} == {"Shprits": 2, "Gel": 0.05}
    c0 = _cost(client, h, sid)                                                     # hali kirim yo'q: narx noma'lum
    assert c0["complete"] is False and set(c0["missing"]) == {"Shprits", "Gel"} and c0["cost"] == 0 and all(m["source"] == "unknown" for m in c0["materials"])
    _receive(client, h, syringe, 100, 450, "S-1")
    _receive(client, h, gel, 10, 20000, "G-1")
    c1 = _cost(client, h, sid)                                                     # 2*450 + 0.05*20000 = 900 + 1000
    assert c1["complete"] is True and c1["missing"] == [] and c1["cost"] == 1900
    assert {m["item"]: (m["unit_cost"], m["cost"], m["source"]) for m in c1["materials"]} == {"Shprits": (450, 900, "stock"), "Gel": (20000, 1000, "stock")}
    assert c1["net_price"] == 100000 and c1["margin"] == 98100 and c1["margin_percent"] == 98.1     # 112000*100/112
    _receive(client, h, syringe, 100, 550, "S-2")                                  # o'rtacha tortilgan narx: (450+550)/2 = 500 -> tannarx o'zgardi
    c2 = _cost(client, h, sid)
    assert c2["materials"][1]["unit_cost"] == 500 and c2["cost"] == 2 * 500 + 1000
    client.post("/warehouse/issues", json={"item_id": syringe, "qty": 200, "reason": "hammasi"}, headers=h)   # qoldiq tugadi: oxirgi kirim narxi
    c3 = _cost(client, h, sid)
    syr = next(m for m in c3["materials"] if m["item"] == "Shprits")
    assert syr["source"] == "last_receipt" and syr["unit_cost"] == 550 and c3["cost"] == 2 * 550 + 1000 and c3["complete"] is True


def test_costs_list_only_services_with_norms_and_replace_semantics(client, auth):
    h = auth("admin")
    with_norm, without = _service(client, h), client.post("/services", json={**SERVICE, "name": "Normasiz"}, headers=h).json()["id"]
    a, b = _item(client, h, "Material A"), _item(client, h, "Material B")
    _receive(client, h, a, 10, 100, "A-1")
    _receive(client, h, b, 10, 300, "B-1")
    client.put(f"/warehouse/services/{with_norm}/materials", headers=h, json={"materials": [{"item_id": a, "qty": 1}, {"item_id": b, "qty": 1}]})
    rows = client.get("/warehouse/service-costs", headers=h).json()
    assert [r["service"] for r in rows] == ["Inyeksiya"] and rows[0]["cost"] == 400
    client.put(f"/warehouse/services/{with_norm}/materials", headers=h, json={"materials": [{"item_id": b, "qty": 2}]})   # almashtiriladi
    assert [m["item"] for m in client.get(f"/warehouse/services/{with_norm}/materials", headers=h).json()] == ["Material B"]
    assert _cost(client, h, with_norm)["cost"] == 600
    client.put(f"/warehouse/services/{with_norm}/materials", headers=h, json={"materials": []})                          # norma olib tashlandi
    c = _cost(client, h, with_norm)
    assert c["cost"] == 0 and c["materials"] == [] and c["complete"] is False and c["margin"] == c["net_price"]
    assert client.get("/warehouse/service-costs", headers=h).json() == []
    assert _cost(client, h, without)["materials"] == []


def test_norm_validation_permissions_and_audit(client, auth):
    h = auth("admin")
    sid = _service(client, h)
    item = _item(client, h, "Material")
    put = lambda body, hh=h, s=sid: client.put(f"/warehouse/services/{s}/materials", json=body, headers=hh)    # noqa: E731
    assert put({"materials": [{"item_id": item, "qty": 0}]}).status_code == 422
    assert put({"materials": [{"item_id": item, "qty": 1}, {"item_id": item, "qty": 2}]}).status_code == 422       # takror
    assert put({"materials": [{"item_id": "00000000-0000-0000-0000-000000000000", "qty": 1}]}).status_code == 422
    assert put({"materials": [{"item_id": item, "qty": 1}]}, auth("nurse")).status_code == 403                    # norma: services:write
    assert put({"materials": [{"item_id": item, "qty": 1}]}, h, "00000000-0000-0000-0000-000000000000").status_code == 404
    assert put({"materials": [{"item_id": item, "qty": 1.5}]}).status_code == 200
    assert client.get(f"/warehouse/services/{sid}/materials", headers=auth("doctor")).json()[0]["qty"] == 1.5
    assert client.get(f"/warehouse/services/{sid}/cost", headers=auth("cashier")).status_code == 403
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AuditLog
    with SessionLocal() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.entity_type == "service_materials")) is not None
