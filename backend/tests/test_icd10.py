import csv

from app.db.session import SessionLocal
from app.services.icd10 import STARTER_CSV, import_csv
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def _emr(client, h, pid, icd=None):
    return client.post("/emr", headers=h, json={"patient_id": pid, "doctor": DOC, "diagnosis": "Test", "prescription": "-",
                                                "visit_date": "2026-11-03", "icd_code": icd})


def test_starter_csv_is_valid_and_seeded(client, auth):
    with open(STARTER_CSV, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    codes = [r["code"] for r in rows]
    assert len(codes) == len(set(codes)) >= 120 and all(r["name_uz"].strip() for r in rows)
    h = auth("doctor")
    found = client.get("/icd10", params={"search": "I10"}, headers=h).json()
    assert found[0]["code"] == "I10" and "gipertenziya" in found[0]["name_uz"].lower()
    assert any(c["code"] == "E11" for c in client.get("/icd10", params={"search": "diabet"}, headers=h).json())
    assert any(c["code"] == "J45" for c in client.get("/icd10", params={"search": "asthma"}, headers=h).json())
    assert client.get("/icd10/e11", headers=h).json()["code"] == "E11"
    assert client.get("/icd10/Z99", headers=h).status_code == 404
    assert len(client.get("/icd10", params={"limit": 5}, headers=h).json()) == 5


def test_import_is_idempotent_and_skips_bad_rows(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("code,name_uz,name_en\nX10.1,Yangi tashxis,New\nbad,Noto'g'ri kod,\nX11,,\nI10,Yangilangan nom,Updated\n",
                    encoding="utf-8")
    with SessionLocal() as db:
        first = import_csv(db, path)
        db.commit()
        second = import_csv(db, path)
        db.commit()
    assert first == {"created": 1, "updated": 1, "skipped": 2}
    assert second == {"created": 0, "updated": 2, "skipped": 2}


def test_emr_icd_code_validated_against_catalog(client, auth):
    h = auth("doctor")
    pid = client.post("/patients", json=NEW, headers=auth("admin")).json()["id"]
    ok = _emr(client, h, pid, "i10")
    assert ok.status_code == 201 and ok.json()["icd_code"] == "I10"          # registrsiz, normallashadi
    assert _emr(client, h, pid, "E11.9").status_code == 201                  # kichik kod: toifasi (E11) bor
    assert _emr(client, h, pid, "Q99").status_code == 422                    # ma'lumotnomada yo'q
    assert _emr(client, h, pid, "xyz").status_code == 422                    # format
    assert _emr(client, h, pid, None).status_code == 201                     # kod ixtiyoriy
    assert client.get("/icd10", headers=auth("cashier")).status_code == 403  # emr:read kerak
