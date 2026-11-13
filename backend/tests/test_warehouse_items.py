"""Ombor katalogi (v1.9.0): dori va sarf materiallari, ruxsatlar, noyoblik, faolsizlantirish, audit."""
import pytest

ITEM = {"name": "Shprits 5 ml", "kind": "Supply", "unit": "dona", "min_qty": 20}


def test_create_list_update_and_never_deleted(client, auth):
    admin = auth("admin")
    made = client.post("/warehouse/items", json={**ITEM, "sku": " SHP-5 "}, headers=admin)
    assert made.status_code == 201
    item = made.json()
    assert item["sku"] == "SHP-5" and item["min_qty"] == 20 and item["kind"] == "Supply" and item["is_active"] is True
    drug = client.post("/warehouse/items", json={"name": "Paratsetamol 500 mg", "kind": "Medicine", "unit": "tabletka"}, headers=admin).json()
    assert drug["min_qty"] == 0
    assert [i["name"] for i in client.get("/warehouse/items", headers=admin).json()] == ["Paratsetamol 500 mg", "Shprits 5 ml"]
    assert [i["name"] for i in client.get("/warehouse/items", params={"kind": "Medicine"}, headers=admin).json()] == ["Paratsetamol 500 mg"]
    assert [i["name"] for i in client.get("/warehouse/items", params={"search": "shp"}, headers=admin).json()] == ["Shprits 5 ml"]    # SKU bo'yicha
    upd = client.put(f"/warehouse/items/{item['id']}", json={"min_qty": 50, "unit": "dona", "is_active": False}, headers=admin).json()
    assert upd["min_qty"] == 50 and upd["is_active"] is False
    assert [i["name"] for i in client.get("/warehouse/items", headers=admin).json()] == ["Paratsetamol 500 mg"]     # faolsiz yashirin
    assert len(client.get("/warehouse/items", params={"include_inactive": True}, headers=admin).json()) == 2
    assert client.delete(f"/warehouse/items/{item['id']}", headers=admin).status_code == 405                         # o'chirish yo'q


def test_uniqueness_and_validation(client, auth):
    admin = auth("admin")
    client.post("/warehouse/items", json={**ITEM, "sku": "A-1"}, headers=admin)
    assert client.post("/warehouse/items", json={**ITEM, "name": "shprits 5 ML"}, headers=admin).status_code == 409      # nom (registrsiz)
    assert client.post("/warehouse/items", json={**ITEM, "name": "Boshqa", "sku": "a-1"}, headers=admin).status_code == 409   # SKU
    assert client.post("/warehouse/items", json={**ITEM, "name": "Sku yo'q 1"}, headers=admin).status_code == 201
    assert client.post("/warehouse/items", json={**ITEM, "name": "Sku yo'q 2", "sku": ""}, headers=admin).status_code == 201   # bo'sh SKU takrorlanadi
    for bad in ({"min_qty": -1}, {"kind": "Food"}, {"unit": ""}, {"name": "x"}, {"min_qty": 1.2345}):
        assert client.post("/warehouse/items", json={**ITEM, "name": "Yaroqsiz", **bad}, headers=admin).status_code == 422, bad
    other = client.post("/warehouse/items", json={**ITEM, "name": "Ikkinchi"}, headers=admin).json()
    assert client.put(f"/warehouse/items/{other['id']}", json={"name": "SHPRITS 5 ml"}, headers=admin).status_code == 409
    assert client.put("/warehouse/items/00000000-0000-0000-0000-000000000000", json={"unit": "x"}, headers=admin).status_code == 404


@pytest.mark.parametrize("role,read,write", [("admin", 200, 201), ("nurse", 200, 201), ("doctor", 200, 403),
                                             ("cashier", 403, 403), ("receptionist", 403, 403)])
def test_permissions(client, auth, role, read, write):
    h = auth(role)
    assert client.get("/warehouse/items", headers=h).status_code == read
    assert client.post("/warehouse/items", json={**ITEM, "name": f"Rol {role}"}, headers=h).status_code == write


def test_changes_are_audited(client, auth):
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AuditLog
    admin = auth("admin")
    item = client.post("/warehouse/items", json=ITEM, headers=admin).json()
    client.put(f"/warehouse/items/{item['id']}", json={"min_qty": 7}, headers=admin)
    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "stock_item")).all()
        assert {r.action for r in rows} == {"create", "update"}
        assert any(float(r.details["changes"]["min_qty"]["to"]) == 7 for r in rows if r.action == "update")
