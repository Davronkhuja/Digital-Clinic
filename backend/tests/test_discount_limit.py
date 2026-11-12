from tests.test_patients import NEW


def _setup(client, auth):
    svc = client.post("/services", headers=auth("admin"), json={"name": "Limit xizmati", "price": 100000, "mxik": "09302001001000000",
                                                               "package_code": "1", "vat_percent": 12}).json()
    pid = client.post("/patients", json={**NEW, "name": "Limit Bemor"}, headers=auth("admin")).json()["id"]
    return svc, pid


def _inv(client, auth, role, svc, pid, **kw):
    return client.post("/invoices", headers=auth(role), json={"patient_id": pid, "lines": [{"service_id": svc["id"], "quantity": 2}],
                                                              "discount_reason": "Doimiy mijoz", **kw})


def test_default_limit_10_cashier_within_and_over(client, auth):
    svc, pid = _setup(client, auth)
    assert client.get("/settings/finance", headers=auth("cashier")).json()["discount_limit_percent"] == 10.0
    assert _inv(client, auth, "cashier", svc, pid, discount_percent=10).status_code == 201                  # aynan limit
    over = _inv(client, auth, "cashier", svc, pid, discount_percent=10.01)
    assert over.status_code == 403 and "finance:discount_override" in over.json()["detail"] and "10" in over.json()["detail"]
    assert _inv(client, auth, "cashier", svc, pid, discount_amount=20000).status_code == 201                # 20000/200000 = 10%
    assert _inv(client, auth, "cashier", svc, pid, discount_amount=20001).status_code == 403                # summa bilan ham foizga aylantiriladi
    admin = _inv(client, auth, "admin", svc, pid, discount_percent=50)
    assert admin.status_code == 201 and admin.json()["discount_total"] == 100000.0                          # override


def test_limit_counts_line_and_invoice_discounts_together(client, auth):
    svc, pid = _setup(client, auth)
    body = {"patient_id": pid, "discount_reason": "Sabab bor", "lines": [{"service_id": svc["id"], "quantity": 2, "discount_percent": 6}],
            "discount_percent": 5}
    res = client.post("/invoices", headers=auth("cashier"), json=body)                                      # 6% va keyin 5%: ~10.7%
    assert res.status_code == 403
    body["discount_percent"] = 4
    assert client.post("/invoices", headers=auth("cashier"), json=body).status_code == 201                  # ~9.76%


def test_reason_mandatory_and_no_discount_needs_nothing(client, auth):
    svc, pid = _setup(client, auth)
    assert client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc["id"]}],
                                                                   "discount_percent": 5}).status_code == 422
    assert client.post("/invoices", headers=auth("admin"), json={"patient_id": pid, "lines": [{"service_id": svc["id"]}],
                                                                 "discount_percent": 50, "discount_reason": " "}).status_code == 422
    assert client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc["id"]}]}).status_code == 201


def test_limit_setting_editable_by_admin_and_affects_only_new_invoices(client, auth):
    svc, pid = _setup(client, auth)
    old = _inv(client, auth, "cashier", svc, pid, discount_percent=10).json()
    assert client.put("/settings/finance", headers=auth("cashier"), json={"discount_limit_percent": 30}).status_code == 403
    assert client.put("/settings/finance", headers=auth("admin"), json={"discount_limit_percent": 101}).status_code == 422
    assert client.put("/settings/finance", headers=auth("admin"), json={"discount_limit_percent": 25}).json()["discount_limit_percent"] == 25.0
    assert _inv(client, auth, "cashier", svc, pid, discount_percent=25).status_code == 201
    assert _inv(client, auth, "cashier", svc, pid, discount_percent=26).status_code == 403
    assert client.get(f"/invoices/{old['id']}", headers=auth("cashier")).json()["discount_total"] == 20000.0   # eski o'zgarmadi
    client.put("/settings/finance", headers=auth("admin"), json={"discount_limit_percent": 0})
    assert _inv(client, auth, "cashier", svc, pid, discount_percent=1).status_code == 403                    # 0: chegirma yo'q
    audit = client.get("/security/audit", params={"entity_type": "settings", "limit": 10}, headers=auth("admin")).json()["items"]
    assert audit and audit[-1]["details"]["discount_limit_percent"]["to"] in ("25.00", "0.00", "25", "0")


def test_draft_update_rechecks_limit(client, auth):
    svc, pid = _setup(client, auth)
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc["id"]}]}).json()
    upd = {"lines": [{"service_id": svc["id"]}], "discount_percent": 40, "discount_reason": "Katta chegirma"}
    assert client.put(f"/invoices/{inv['id']}", headers=auth("cashier"), json=upd).status_code == 403
    assert client.put(f"/invoices/{inv['id']}", headers=auth("admin"), json=upd).status_code == 200
