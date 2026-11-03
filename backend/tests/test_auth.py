import time

import jwt

from app.core.config import settings
from tests.conftest import DEMO_USERS, PASSWORD, login


def test_login_ok_returns_user_and_tokens(client):
    data = login(client, "admin")
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "admin"
    assert "patients:read" in data["user"]["permissions"]


def test_login_wrong_password_and_unknown_email(client):
    assert client.post("/auth/login", json={"email": DEMO_USERS["admin"], "password": "wrongpass"}).status_code == 401
    assert client.post("/auth/login", json={"email": "nobody@clinic.uz", "password": PASSWORD}).status_code == 401


def test_no_token_and_garbage_token_are_401(client):
    assert client.get("/patients").status_code == 401
    assert client.get("/patients", headers={"Authorization": "Bearer bad.token.value"}).status_code == 401


def test_expired_access_token_is_401(client):
    user = login(client)["user"]
    token = jwt.encode(
        {"sub": user["id"], "type": "access", "exp": int(time.time()) - 5},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    assert client.get("/patients", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_and_vice_versa(client):
    data = login(client)
    assert client.get("/patients", headers={"Authorization": f"Bearer {data['refresh_token']}"}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": data["access_token"]}).status_code == 401


def test_refresh_rotates_tokens(client):
    first = login(client)
    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    new = second.json()
    assert new["refresh_token"] != first["refresh_token"]
    assert client.get("/patients", headers={"Authorization": f"Bearer {new['access_token']}"}).status_code == 200


def test_reusing_rotated_refresh_token_revokes_whole_family(client):
    first = login(client)
    new = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()
    # eski (allaqachon aylantirilgan) token qayta ishlatildi -> o'g'irlik belgisi
    assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    # oiladagi yangi token ham bekor qilingan
    assert client.post("/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401


def test_logout_revokes_refresh_token(client):
    data = login(client)
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert client.post("/auth/logout", json={"refresh_token": data["refresh_token"]}, headers=headers).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]}).status_code == 401


def test_change_password_revokes_all_refresh_tokens(client):
    a = login(client)
    b = login(client)  # ikkinchi qurilma
    headers = {"Authorization": f"Bearer {a['access_token']}"}
    res = client.post("/auth/change-password", headers=headers,
                      json={"current_password": PASSWORD, "new_password": "newpassword1"})
    assert res.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": a["refresh_token"]}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": b["refresh_token"]}).status_code == 401
    assert client.post("/auth/login", json={"email": DEMO_USERS["admin"], "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": DEMO_USERS["admin"], "password": "newpassword1"}).status_code == 200


def test_change_password_requires_correct_current_password(client):
    data = login(client)
    res = client.post("/auth/change-password", headers={"Authorization": f"Bearer {data['access_token']}"},
                      json={"current_password": "not-the-password", "new_password": "newpassword1"})
    assert res.status_code == 400


def test_inactive_user_cannot_login(client, auth):
    users = client.get("/users", headers=auth("admin")).json()
    nurse = next(u for u in users if u["email"] == DEMO_USERS["nurse"])
    assert client.patch(f"/users/{nurse['id']}", json={"is_active": False}, headers=auth("admin")).status_code == 200
    res = client.post("/auth/login", json={"email": DEMO_USERS["nurse"], "password": PASSWORD})
    assert res.status_code == 403


def test_forgot_password_is_honest(client):
    assert client.post("/auth/forgot-password", json={"email": DEMO_USERS["admin"]}).status_code == 501
