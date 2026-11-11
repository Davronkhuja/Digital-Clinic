from tests.conftest import reset_data

NEW = {"name": "Test Bemor", "phone": "+998 90 000 0000", "age": 30, "gender": "male"}


def test_patient_crud(client, auth):
    h = auth("receptionist")
    created = client.post("/patients", json={**NEW, "doctor": "Dr. Behruz Rustamov"}, headers=h)
    assert created.status_code == 201
    p = created.json()
    assert p["age"] == 30 and p["doctor"] == "Dr. Behruz Rustamov"

    assert client.get(f"/patients/{p['id']}", headers=h).json()["name"] == "Test Bemor"
    upd = client.put(f"/patients/{p['id']}", json={"phone": "+998 91 111 1111", "blood_type": "A+"}, headers=h)
    assert upd.status_code == 200 and upd.json()["phone"] == "+998 91 111 1111"
    assert upd.json()["name"] == "Test Bemor"  # yuborilmagan maydonlar o'zgarmaydi

    assert client.delete(f"/patients/{p['id']}", headers=auth("admin")).status_code == 200
    assert client.get(f"/patients/{p['id']}", headers=h).status_code == 404


def test_pinfl_validation_422(client, auth):
    h = auth("admin")
    for bad in ("123", "1234567890123a", "123456789012345"):
        assert client.post("/patients", json={**NEW, "pinfl": bad}, headers=h).status_code == 422, bad


def test_pinfl_unique_409_and_null_allowed_many_times(client, auth):
    h = auth("admin")
    assert client.post("/patients", json={**NEW, "pinfl": "12345678901234"}, headers=h).status_code == 201
    dup = client.post("/patients", json={**NEW, "name": "Boshqa Bemor", "pinfl": "12345678901234"}, headers=h)
    assert dup.status_code == 409
    # pinfl bo'lmagan bemorlar ko'p bo'lishi mumkin
    assert client.post("/patients", json={**NEW, "name": "Pinflsiz Bir"}, headers=h).status_code == 201
    assert client.post("/patients", json={**NEW, "name": "Pinflsiz Ikki"}, headers=h).status_code == 201


def test_pinfl_dup_on_update_409(client, auth):
    h = auth("admin")
    a = client.post("/patients", json={**NEW, "name": "A Bemor", "pinfl": "11111111111111"}, headers=h).json()
    b = client.post("/patients", json={**NEW, "name": "B Bemor", "pinfl": "22222222222222"}, headers=h).json()
    assert client.put(f"/patients/{b['id']}", json={"pinfl": a["pinfl"]}, headers=h).status_code == 409


def test_age_or_birth_date_required(client, auth):
    body = {k: v for k, v in NEW.items() if k != "age"}
    assert client.post("/patients", json=body, headers=auth("admin")).status_code == 422


def test_unknown_doctor_is_422(client, auth):
    res = client.post("/patients", json={**NEW, "doctor": "Dr. Yo'q"}, headers=auth("admin"))
    assert res.status_code == 422


def test_search_by_name_phone_and_pinfl(client, auth):
    h = auth("admin")
    client.post("/patients", json={**NEW, "pinfl": "98765432109876", "phone": "+998 77 777 7777"}, headers=h)
    for q in ("Aziza", "777 7777", "98765432109876"):
        assert client.get("/patients", params={"search": q}, headers=h).json(), q
    assert client.get("/patients", params={"search": "yo'qbunaqa"}, headers=h).json() == []


def test_limit_is_capped_at_100(client, auth):
    assert client.get("/patients", params={"limit": 200}, headers=auth("admin")).status_code == 422


def test_patient_with_records_cannot_be_deleted(client, auth):
    h = auth("admin")
    aziza = next(p for p in client.get("/patients", params={"limit": 100}, headers=h).json() if p["name"] == "Aziza Karimova")
    assert client.delete(f"/patients/{aziza['id']}", headers=h).status_code == 409


def test_invalid_uuid_in_path_is_422(client, auth):
    assert client.get("/patients/1", headers=auth("admin")).status_code == 422


def test_appointments_filter_by_patient_and_doctor_name_join(client, auth):
    h = auth("admin")
    aziza = next(p for p in client.get("/patients", params={"limit": 100}, headers=h).json() if p["name"] == "Aziza Karimova")
    appts = client.get("/appointments", params={"patient_id": aziza["id"]}, headers=h).json()
    assert appts and all(a["patient_id"] == aziza["id"] for a in appts)
    assert all(a["patient_name"] == "Aziza Karimova" and a["doctor"].startswith("Dr.") for a in appts)


def test_create_appointment_encounter_and_transaction_use_joins(client, auth):
    admin = auth("admin")
    p = client.post("/patients", json=NEW, headers=admin).json()
    appt = client.post("/appointments", headers=admin, json={
        "patient_id": p["id"], "doctor": "Dr. Behruz Rustamov", "date": "2026-12-01", "time": "10:00", "type": "Konsultatsiya"})
    assert appt.status_code == 201 and appt.json()["patient_name"] == "Test Bemor"
    emr = client.post("/emr", headers=auth("doctor"), json={
        "patient_id": p["id"], "doctor": "Dr. Behruz Rustamov", "diagnosis": "Test", "prescription": "Aspirin",
        "visit_date": "2026-11-03"})
    assert emr.status_code == 201 and emr.json()["prescription"] == "Aspirin"
    tx = client.post("/finance/transactions", headers=auth("cashier"), json={
        "type": "income", "amount": 123456.78, "description": "t", "category": "Lab", "date": "2026-11-03",
        "patient_name": "Test Bemor"})
    assert tx.status_code == 201 and tx.json()["amount"] == 123456.78


def test_data_survives_restart_and_seed_is_idempotent(client, auth):
    """'Restart': ulanishlar yopiladi, seed qayta ishga tushadi; yozilgan ma'lumot saqlanib qoladi, dublikat yo'q."""
    from app.db.session import engine
    from app.seed import main as seed_main

    h = auth("admin")
    created = client.post("/patients", json={**NEW, "name": "Restart Bemor"}, headers=h).json()
    before = len(client.get("/patients", params={"limit": 100}, headers=h).json())
    users_before = len(client.get("/users", headers=h).json())

    engine.dispose()
    seed_main()  # konteyner startidagi seed

    h = auth("admin")
    after = client.get("/patients", params={"limit": 100}, headers=h).json()
    assert len(after) == before and created["id"] in {p["id"] for p in after}
    assert len(client.get("/users", headers=h).json()) == users_before


def test_reset_helper_gives_clean_slate():
    reset_data()


def test_search_phone_digits_and_birth_date(client, auth):
    h = auth("admin")
    client.post("/patients", json={**NEW, "name": "Qidiruv Sinov", "phone": "+998 (93) 555-12-34",
                                   "birth_date": "1990-05-17"}, headers=h)
    for q in ("998935551234", "93 555 12", "555-12-34", "1990-05-17", "17.05.1990"):
        names = [p["name"] for p in client.get("/patients", params={"search": q}, headers=h).json()]
        assert "Qidiruv Sinov" in names, q
    assert client.get("/patients", params={"search": "18.05.1990"}, headers=h).json() == []


def test_duplicates_by_phone_and_birth_date(client, auth):
    h = auth("receptionist")
    a = {**NEW, "name": "Dublikat Bemor", "phone": "+998 90 111 22 33", "birth_date": "1985-01-01"}
    client.post("/patients", json=a, headers=h)
    client.post("/patients", json={**a, "name": "dublikat bemor ", "phone": "998901112233"}, headers=h)
    client.post("/patients", json={**NEW, "name": "Yakka Bemor", "phone": "+998 90 999 99 99"}, headers=h)
    groups = client.get("/patients/duplicates", headers=h).json()
    mine = [g for g in groups if g["patients"][0]["name"].lower().strip() == "dublikat bemor"]
    assert len(mine) == 1 and len(mine[0]["patients"]) == 2
    assert set(mine[0]["reasons"]) == {"phone", "birth_date"}
    assert all("Yakka" not in p["name"] for g in groups for p in g["patients"])


def test_merge_moves_records_and_deactivates_source(client, auth):
    admin = auth("admin")
    keep = client.post("/patients", json={**NEW, "name": "Asosiy Bemor"}, headers=admin).json()
    dup = client.post("/patients", json={**NEW, "name": "Dublikat Bemor", "pinfl": "55555555555555",
                                         "blood_type": "B+"}, headers=admin).json()
    appt = client.post("/appointments", headers=admin, json={
        "patient_id": dup["id"], "doctor": "Dr. Behruz Rustamov", "date": "2026-12-01", "time": "10:00",
        "type": "Konsultatsiya"}).json()
    emr = client.post("/emr", headers=auth("doctor"), json={
        "patient_id": dup["id"], "doctor": "Dr. Behruz Rustamov", "diagnosis": "Test", "prescription": "Aspirin",
        "visit_date": "2026-11-03"}).json()

    res = client.post(f"/patients/{keep['id']}/merge", json={"source_id": dup["id"]}, headers=admin)
    assert res.status_code == 200
    merged = res.json()
    assert merged["pinfl"] == "55555555555555" and merged["blood_type"] == "B+"  # bo'sh maydonlar to'ldirildi

    src = client.get(f"/patients/{dup['id']}", headers=admin).json()  # o'chirilmagan
    assert src["status"] == "Inactive" and src["merged_into"] == keep["id"] and src["pinfl"] is None
    assert client.get("/appointments", params={"patient_id": keep["id"]}, headers=admin).json()[0]["id"] == appt["id"]
    assert client.get("/appointments", params={"patient_id": dup["id"]}, headers=admin).json() == []
    assert client.get(f"/emr/{emr['id']}", headers=admin).json()["patient_id"] == keep["id"]

    audit = client.get("/security/audit", params={"entity_type": "patient", "limit": 50}, headers=admin).json()["items"]
    assert any(e["action"] == "merge" and e["entity_id"] == keep["id"] for e in audit)

    # qayta birlashtirib bo'lmaydi; o'zi bilan ham
    assert client.post(f"/patients/{keep['id']}/merge", json={"source_id": dup["id"]}, headers=admin).status_code == 409
    assert client.post(f"/patients/{keep['id']}/merge", json={"source_id": keep["id"]}, headers=admin).status_code == 422


def test_merge_requires_merge_permission(client, auth):
    a = client.post("/patients", json=NEW, headers=auth("admin")).json()
    b = client.post("/patients", json={**NEW, "name": "Ikkinchi"}, headers=auth("admin")).json()
    body = {"source_id": b["id"]}
    assert client.post(f"/patients/{a['id']}/merge", json=body, headers=auth("doctor")).status_code == 403
    assert client.post(f"/patients/{a['id']}/merge", json=body, headers=auth("receptionist")).status_code == 200
    # patients:delete endi birlashtirish uchun talab qilinmaydi
    perms = client.get("/auth/me", headers=auth("receptionist")).json().get("permissions", [])
    assert "patients:merge" in perms and "patients:delete" not in perms
