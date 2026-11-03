from tests.conftest import DEMO_USERS, PASSWORD, login

NEW = {"name": "Audit Bemor", "phone": "+998 90 000 0000", "age": 30, "gender": "male"}


def _audit(client, auth, **params):
    res = client.get("/security/audit", params={"limit": 200, **params}, headers=auth("admin"))
    assert res.status_code == 200, res.text
    return res.json()["items"]


def test_patient_read_and_write_are_audited_with_ip_and_user(client, auth):
    doctor = auth("doctor")
    p = client.post("/patients", json=NEW, headers=doctor).json()
    client.get(f"/patients/{p['id']}", headers=doctor)
    client.get("/patients", headers=doctor)
    client.put(f"/patients/{p['id']}", json={"phone": "+998 91 111 1111"}, headers=doctor)

    entries = [e for e in _audit(client, auth, entity_type="patient") if e["user_name"] == "Dr. Behruz Rustamov"]
    actions = {e["action"] for e in entries}
    assert {"create", "read", "update"} <= actions
    created = next(e for e in entries if e["action"] == "create")
    assert created["entity_id"] == p["id"] and created["ip"]
    update = next(e for e in entries if e["action"] == "update")
    assert update["details"] == {"fields": ["phone"]}


def test_emr_and_transaction_are_audited(client, auth):
    admin = auth("admin")
    p = client.post("/patients", json=NEW, headers=admin).json()
    emr = client.post("/emr", headers=auth("doctor"), json={
        "patient_id": p["id"], "doctor": "Dr. Behruz Rustamov", "diagnosis": "x", "prescription": "y", "visit_date": "2026-11-03"}).json()
    tx = client.post("/finance/transactions", headers=auth("cashier"), json={
        "type": "income", "amount": 1000, "description": "t", "category": "Lab", "date": "2026-11-03"}).json()
    client.get("/emr", headers=auth("doctor"))
    client.get("/finance/transactions", headers=auth("cashier"))

    assert any(e["action"] == "create" and e["entity_id"] == emr["id"] for e in _audit(client, auth, entity_type="emr"))
    assert any(e["action"] == "read" for e in _audit(client, auth, entity_type="emr"))
    assert any(e["action"] == "create" and e["entity_id"] == tx["id"] for e in _audit(client, auth, entity_type="transaction"))
    assert any(e["action"] == "read" for e in _audit(client, auth, entity_type="transaction"))


def test_login_events_including_failures(client, auth):
    client.post("/auth/login", json={"email": DEMO_USERS["nurse"], "password": "wrong-password"})
    client.post("/auth/login", json={"email": "ghost@clinic.uz", "password": "whatever123"})
    login(client, "nurse")
    entries = _audit(client, auth, entity_type="auth")
    failed = [e for e in entries if e["action"] == "login_failed"]
    assert len(failed) == 2 and {e["details"]["email"] for e in failed} == {DEMO_USERS["nurse"], "ghost@clinic.uz"}
    assert any(e["action"] == "login" and e["user_name"] == "Malika Yusupova" for e in entries)
    assert all("password" not in str(e["details"]).lower() for e in entries)  # parol jurnalga tushmaydi


def test_audit_requires_permission_and_supports_filter_and_paging(client, auth):
    for role in ("doctor", "nurse", "receptionist", "cashier"):
        assert client.get("/security/audit", headers=auth(role)).status_code == 403
    client.get("/patients", headers=auth("doctor"))
    page = client.get("/security/audit", params={"limit": 1}, headers=auth("admin")).json()
    assert len(page["items"]) == 1 and page["total"] >= 2
    assert client.get("/security/audit", params={"limit": 500}, headers=auth("admin")).status_code == 422


def test_report_download_is_audited(client, auth):
    client.get("/reports/download/2", headers=auth("admin"))
    assert any(e["details"] == {"report_id": "2", "rows": 5} for e in _audit(client, auth, entity_type="report"))


def test_forwarded_for_only_trusted_from_proxy(client, auth):
    # TestClient manzili ('testclient') ishonchli proksi emas: soxta X-Forwarded-For e'tiborga olinmaydi
    client.get("/patients", headers={**auth("doctor"), "X-Forwarded-For": "6.6.6.6"})
    entry = next(e for e in _audit(client, auth, entity_type="patient") if e["action"] == "read")
    assert entry["ip"] != "6.6.6.6"


def test_client_ip_walks_forwarded_chain_from_the_right():
    from types import SimpleNamespace

    from app.services.audit import client_ip

    def req(peer, xff):
        return SimpleNamespace(client=SimpleNamespace(host=peer), headers={"x-forwarded-for": xff} if xff else {})

    assert client_ip(req("172.18.0.5", "203.0.113.9")) == "203.0.113.9"
    # chapdagi qiymatni mijoz soxtalashtirgan: o'ngdan birinchi ishonchsiz manzil olinadi
    assert client_ip(req("172.18.0.5", "6.6.6.6, 203.0.113.9")) == "203.0.113.9"
    assert client_ip(req("198.51.100.7", "6.6.6.6")) == "198.51.100.7"  # ishonchsiz peer
    assert client_ip(req("172.18.0.5", None)) == "172.18.0.5"


def test_sessions_list_and_admin_can_revoke(client, auth):
    nurse = login(client, "nurse")
    nurse_headers = {"Authorization": f"Bearer {nurse['access_token']}"}
    admin = auth("admin")

    all_sessions = client.get("/security/sessions", headers=admin).json()
    target = next(s for s in all_sessions if s["email"] == DEMO_USERS["nurse"])
    assert target["user_name"] == "Malika Yusupova" and target["ip"]
    assert client.get("/security/sessions", headers=nurse_headers).status_code == 403

    assert client.delete(f"/security/sessions/{target['id']}", headers=admin).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": nurse["refresh_token"]}).status_code == 401
    assert all(s["id"] != target["id"] for s in client.get("/security/sessions", headers=admin).json())
    assert any(e["action"] == "revoke_session" for e in _audit(client, auth, entity_type="session"))


def test_user_can_list_and_revoke_only_own_sessions(client):
    a = login(client, "nurse")
    ha = {"Authorization": f"Bearer {a['access_token']}"}
    login(client, "doctor")
    mine = client.get("/auth/sessions", headers=ha).json()
    assert mine and all(s["email"] == DEMO_USERS["nurse"] for s in mine)

    doctor_headers = {"Authorization": f"Bearer {login(client, 'doctor')['access_token']}"}
    # begona sessiyani bekor qila olmaydi (404: mavjudligi ham oshkor qilinmaydi)
    assert client.delete(f"/auth/sessions/{mine[0]['id']}", headers=doctor_headers).status_code == 404
    assert client.delete(f"/auth/sessions/{mine[0]['id']}", headers=ha).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": a["refresh_token"]}).status_code == 401


def test_role_and_user_changes_are_audited(client, auth):
    admin = auth("admin")
    role = next(r for r in client.get("/roles", headers=admin).json() if r["code"] == "nurse")
    client.put(f"/roles/{role['id']}", json={"permissions": ["patients:read"]}, headers=admin)
    client.post("/users", headers=admin, json={"name": "Yangi Qabul", "email": "yangi@clinic.uz", "password": PASSWORD + "x", "role": "receptionist"})
    assert any(e["action"] == "update" for e in _audit(client, auth, entity_type="role"))
    assert any(e["action"] == "create" for e in _audit(client, auth, entity_type="user"))
