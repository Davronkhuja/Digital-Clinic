import pytest

from tests.conftest import DEMO_USERS

ROLES = list(DEMO_USERS)

# (nom, metod, yo'l, ruxsat etilgan rollar). Ruxsat etilganda 403 bo'lmasligi, aks holda aynan 403 bo'lishi kerak.
MATRIX = [
    ("patients read", "GET", "/patients", {"admin", "doctor", "nurse", "receptionist", "cashier"}),
    ("patients write", "POST", "/patients", {"admin", "doctor", "nurse", "receptionist"}),
    ("appointments read", "GET", "/appointments", {"admin", "doctor", "nurse", "receptionist", "cashier"}),
    ("appointments write", "POST", "/appointments", {"admin", "doctor", "nurse", "receptionist"}),
    ("emr read", "GET", "/emr", {"admin", "doctor", "nurse"}),
    ("emr write", "POST", "/emr", {"admin", "doctor"}),
    ("finance read", "GET", "/finance/transactions", {"admin", "cashier"}),
    ("finance summary", "GET", "/finance/summary", {"admin", "cashier"}),
    ("finance write", "POST", "/finance/transactions", {"admin", "cashier"}),
    ("staff read", "GET", "/staff", {"admin", "doctor", "nurse", "receptionist", "cashier"}),
    ("staff write", "POST", "/staff", {"admin"}),
    ("settings read", "GET", "/settings", {"admin", "doctor", "nurse", "receptionist", "cashier"}),
    ("settings write", "PUT", "/settings", {"admin"}),
    ("analytics", "GET", "/analytics/dashboard", {"admin", "doctor", "cashier"}),
    ("reports", "GET", "/reports", {"admin", "doctor", "cashier"}),
    ("ai", "GET", "/ai/status", {"admin", "doctor", "nurse"}),
    ("roles", "GET", "/roles", {"admin"}),
    ("users", "GET", "/users", {"admin"}),
]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("name,method,path,allowed", MATRIX, ids=[m[0] for m in MATRIX])
def test_permission_matrix(client, auth, role, name, method, path, allowed):
    kwargs = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
    res = client.request(method, path, headers=auth(role), **kwargs)
    if role in allowed:
        assert res.status_code != 403, f"{role} {method} {path}: {res.text}"
    else:
        assert res.status_code == 403, f"{role} {method} {path} -> {res.status_code}"


def test_delete_patient_needs_dedicated_permission(client, auth):
    patients = client.get("/patients", headers=auth("admin")).json()
    pid = patients[0]["id"]
    assert client.delete(f"/patients/{pid}", headers=auth("receptionist")).status_code == 403
    assert client.delete(f"/patients/{pid}", headers=auth("doctor")).status_code == 403


def test_changing_role_permissions_takes_effect_immediately(client, auth):
    admin = auth("admin")
    roles = {r["code"]: r for r in client.get("/roles", headers=admin).json()}
    nurse = roles["nurse"]
    perms = [p for p in nurse["permissions"] if p != "emr:read"]
    res = client.put(f"/roles/{nurse['id']}", json={"permissions": perms}, headers=admin)
    assert res.status_code == 200
    assert client.get("/emr", headers=auth("nurse")).status_code == 403


def test_admin_role_cannot_be_modified(client, auth):
    admin = auth("admin")
    role = next(r for r in client.get("/roles", headers=admin).json() if r["code"] == "admin")
    assert client.put(f"/roles/{role['id']}", json={"permissions": []}, headers=admin).status_code == 400


def test_unknown_permission_is_rejected(client, auth):
    admin = auth("admin")
    role = next(r for r in client.get("/roles", headers=admin).json() if r["code"] == "nurse")
    assert client.put(f"/roles/{role['id']}", json={"permissions": ["nope:nope"]}, headers=admin).status_code == 422


def test_admin_cannot_demote_or_deactivate_self(client, auth):
    admin = auth("admin")
    me = next(u for u in client.get("/users", headers=admin).json() if u["email"] == DEMO_USERS["admin"])
    assert client.patch(f"/users/{me['id']}", json={"is_active": False}, headers=admin).status_code == 400
    assert client.patch(f"/users/{me['id']}", json={"role": "nurse"}, headers=admin).status_code == 400
