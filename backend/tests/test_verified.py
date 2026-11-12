from pathlib import Path

from app.db.session import SessionLocal
from app.services import icd10, inn
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def test_starter_records_are_unverified_with_source(client, auth):
    h = auth("doctor")
    code = client.get("/icd10/I10", headers=h).json()
    assert code["verified"] is False and code["source"] == "starter (namuna)"
    drug = client.get("/inn", params={"search": "amlodipine"}, headers=h).json()[0]
    assert drug["verified"] is False and drug["source"] == "starter (namuna)"
    tests = client.get("/lab/tests", headers=h).json()
    assert all(not t["verified"] and t["source"] == "starter (namuna)" for t in tests)
    assert all(not r["verified"] and r["source"] == "starter (namuna)" for t in tests for r in t["ranges"])


def test_official_import_marks_verified_and_starter_file_does_not(tmp_path):
    official = tmp_path / "official.csv"
    official.write_text("code,name_uz\nI10,Rasmiy nom\nX99,Yangi\n", encoding="utf-8")
    with SessionLocal() as db:
        icd10.import_csv(db, official, verified=True, source="MKB-10 rasmiy 2024")
        db.commit()
    with SessionLocal() as db:
        from sqlalchemy import select

        from app.models import Icd10Code
        rows = {c.code: c for c in db.scalars(select(Icd10Code).where(Icd10Code.code.in_(["I10", "X99", "E11"])))}
        assert rows["I10"].verified and rows["I10"].source == "MKB-10 rasmiy 2024" and rows["I10"].name_uz == "Rasmiy nom"
        assert rows["X99"].verified
        assert rows["E11"].verified is False                                        # tegilmagan starter yozuv namuna qoladi
        starter = tmp_path / "inn_starter.csv"
        starter.write_text("inn\nparacetamol\n", encoding="utf-8")
        inn.import_csv(db, starter, verified=False, source=starter.name)
        db.commit()


def test_import_scripts_choose_verified_by_filename(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys

    path = Path(__file__).resolve().parent.parent / "scripts" / "import_inn.py"
    spec = importlib.util.spec_from_file_location("import_inn_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    official, starter = tmp_path / "inn_official.csv", tmp_path / "my_starter.csv"
    official.write_text("inn,group_uz\nnewdrugone,Guruh\n", encoding="utf-8")
    starter.write_text("inn,group_uz\nnewdrugtwo,Guruh\n", encoding="utf-8")
    for f, expect in ((official, "tasdiqlangan"), (starter, "namuna")):
        monkeypatch.setattr(sys, "argv", ["import_inn.py", str(f), "--source", "Test manba"])
        module.main()
        assert expect in capsys.readouterr().out
    with SessionLocal() as db:
        one, two = inn.canonical(db, "newdrugone"), inn.canonical(db, "newdrugtwo")
        assert one.verified and one.source == "Test manba" and two.verified is False


def test_admin_verify_endpoints(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    assert client.post("/icd10/verify", headers=doc, json={"items": ["I10"], "source": "Dr. tekshirdi"}).status_code == 403
    assert client.post("/icd10/verify", headers=admin, json={"source": "Dr. tekshirdi"}).status_code == 422          # items/all yo'q
    assert client.post("/icd10/verify", headers=admin, json={"items": ["i10", "E11"], "source": "Rasmiy ro'yxat bilan solishtirildi"}).json() == {"verified": 2}
    i10 = client.get("/icd10/I10", headers=doc).json()
    assert i10["verified"] is True and i10["source"] == "Rasmiy ro'yxat bilan solishtirildi"
    assert client.get("/icd10/J06", headers=doc).json()["verified"] is False
    assert client.post("/inn/verify", headers=admin, json={"items": ["AMLODIPINE"], "source": "Tekshirildi"}).json() == {"verified": 1}
    assert client.get("/inn", params={"search": "amlodipine"}, headers=doc).json()[0]["verified"] is True
    total = client.post("/inn/verify", headers=admin, json={"all": True, "source": "To'liq tekshiruv"}).json()["verified"]
    assert total > 100
    assert client.post("/inn/verify", headers=admin, json={"all": True, "source": "To'liq tekshiruv"}).json() == {"verified": 0}
    audit = client.get("/security/audit", params={"entity_type": "icd10", "limit": 10}, headers=admin).json()["items"]
    assert audit and audit[0]["action"] == "update"


def test_lab_ranges_editable_by_admin_and_result_carries_ref_verified(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    pid = client.post("/patients", json={**NEW, "name": "Me'yor Bemor", "gender": "male", "birth_date": "1990-01-01", "age": None},
                      headers=admin).json()["id"]
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=doc).json()}
    glu = tests["GLU"]

    def result():
        order = client.post("/lab/orders", headers=doc, json={"patient_id": pid, "doctor": DOC, "test_ids": [glu["id"]]}).json()
        return client.put(f"/lab/orders/{order['id']}/results", headers=doc,
                          json={"results": [{"item_id": order["items"][0]["id"], "value": 6.5}]}).json()["items"][0], order["id"]

    first, first_order = result()
    assert first["flag"] == "High" and first["ref_verified"] is False                       # namuna me'yor bilan
    # laboratoriya o'z analizatoriga moslab me'yorni o'zgartiradi (admin, Sozlamalar)
    res = client.put(f"/lab/tests/{glu['id']}", headers=admin, json={
        "verified": True, "source": "Analizator Mindray BS-240 yo'riqnomasi",
        "ranges": [{"low": 4.1, "high": 7.0, "source": "Mindray BS-240", "verified": True}]})
    assert res.status_code == 200 and res.json()["verified"] is True and res.json()["ranges"][0]["verified"] is True
    second, _ = result()
    assert second["flag"] == "Normal" and second["ref_verified"] is True and second["reference"] == "4.1 - 7"
    # eski natija o'zgarmagan: namuna me'yor bilan qolgan
    old = client.get(f"/lab/orders/{first_order}", headers=admin).json()["items"][0]
    assert old["flag"] == "High" and old["ref_verified"] is False and old["reference"] == "3.9 - 5.9"
    # me'yorni qo'lda kiritgan, source bermagan: standart manba
    again = client.put(f"/lab/tests/{glu['id']}", headers=admin, json={"ranges": [{"low": 4.0, "high": 6.0}]}).json()
    assert again["ranges"][0]["verified"] is True and "klinika" in again["ranges"][0]["source"]
    # doktor me'yorni tahrirlay olmaydi
    assert client.put(f"/lab/tests/{glu['id']}", headers=doc, json={"verified": True}).status_code == 403


def test_pdf_warns_when_reference_unverified(client, auth):
    import io

    from pypdf import PdfReader
    doc = auth("doctor")
    pid = client.post("/patients", json=NEW, headers=auth("admin")).json()["id"]
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=doc).json()}
    order = client.post("/lab/orders", headers=doc, json={"patient_id": pid, "doctor": DOC, "test_ids": [tests["ALT"]["id"]]}).json()
    client.put(f"/lab/orders/{order['id']}/results", headers=doc, json={"results": [{"item_id": order["items"][0]["id"], "value": 20}]})
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(client.get(f"/lab/orders/{order['id']}/pdf", headers=doc).content)).pages)
    assert "namuna" in text
