import io

from app.core.config import settings
from tests.test_patients import NEW

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
DICOM = b"\x00" * 128 + b"DICM" + b"\x00" * 32
DOC = "Dr. Behruz Rustamov"


def _patient(client, auth, name="Fayl Bemor"):
    return client.post("/patients", json={**NEW, "name": name}, headers=auth("admin")).json()["id"]


def _upload(client, auth, pid, data=PDF, name="tahlil.pdf", role="doctor", **form):
    return client.post(f"/patients/{pid}/attachments", headers=auth(role), data=form,
                       files={"file": (name, io.BytesIO(data), "application/octet-stream")})


def test_upload_list_download_roundtrip_with_audit(client, auth):
    pid = _patient(client, auth)
    res = _upload(client, auth, pid, note="Qon tahlili")
    assert res.status_code == 201
    a = res.json()
    assert (a["filename"], a["content_type"], a["size_bytes"], a["note"]) == ("tahlil.pdf", "application/pdf", len(PDF), "Qon tahlili")
    assert a["uploaded_by"] == DOC and a["encounter_id"] is None
    listed = client.get(f"/patients/{pid}/attachments", headers=auth("nurse")).json()
    assert [x["id"] for x in listed] == [a["id"]]
    dl = client.get(f"/attachments/{a['id']}/download", headers=auth("nurse"))
    assert dl.status_code == 200 and dl.content == PDF and dl.headers["content-type"] == "application/pdf"
    assert "attachment" in dl.headers["content-disposition"] and dl.headers["x-content-type-options"] == "nosniff"
    audit = client.get("/security/audit", params={"entity_type": "attachment", "limit": 50}, headers=auth("admin")).json()["items"]
    assert {"create", "read"} <= {e["action"] for e in audit}
    assert any((e.get("details") or {}).get("download") for e in audit)


def test_all_allowed_types_detected_by_content_not_name_or_header(client, auth):
    pid = _patient(client, auth)
    for data, name, ctype in ((PNG, "rasm.exe", "image/png"), (JPG, "x", "image/jpeg"), (DICOM, "kt.bin", "application/dicom"),
                              (PDF, "../../etc/passwd", "application/pdf")):
        res = _upload(client, auth, pid, data, name)
        assert res.status_code == 201, name
        assert res.json()["content_type"] == ctype
    names = {a["filename"] for a in client.get(f"/patients/{pid}/attachments", headers=auth("doctor")).json()}
    assert names == {"passwd.pdf", "rasm.png", "x.jpg", "kt.dcm"}
    assert not any("/" in n or ".." in n for n in names)                      # yo'l ajratgichlar olib tashlangan


def test_rejects_bad_type_empty_and_too_large(client, auth, monkeypatch):
    pid = _patient(client, auth)
    assert _upload(client, auth, pid, b"MZ\x90\x00 bu exe", "virus.pdf").status_code == 415   # kengaytma pdf, lekin pdf emas
    assert _upload(client, auth, pid, b"<script>alert(1)</script>", "x.png").status_code == 415
    assert _upload(client, auth, pid, b"", "bosh.pdf").status_code == 422
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    ok = _upload(client, auth, pid, PDF + b"0" * (1024 * 1024 - len(PDF)))                    # aynan 1 MB
    assert ok.status_code == 201
    big = _upload(client, auth, pid, PDF + b"0" * (1024 * 1024))
    assert big.status_code == 413
    assert len(client.get(f"/patients/{pid}/attachments", headers=auth("doctor")).json()) == 1


def test_encounter_link_filter_and_ownership(client, auth):
    admin, doc = auth("admin"), auth("doctor")
    pid, other = _patient(client, auth), _patient(client, auth, "Boshqa Bemor")
    enc = client.post("/emr", headers=doc, json={"patient_id": pid, "doctor": DOC, "diagnosis": "x", "prescription": "-",
                                                  "visit_date": "2026-12-01"}).json()
    assert _upload(client, auth, pid, encounter_id=enc["id"]).status_code == 201
    assert _upload(client, auth, pid).status_code == 201                                       # kartaga (ko'riksiz)
    assert _upload(client, auth, other, encounter_id=enc["id"]).status_code == 422             # boshqa bemorning ko'rigi
    assert len(client.get(f"/patients/{pid}/attachments", headers=admin).json()) == 2
    only = client.get(f"/patients/{pid}/attachments", params={"encounter_id": enc["id"]}, headers=admin).json()
    assert len(only) == 1 and only[0]["encounter_id"] == enc["id"]
    assert client.get(f"/patients/{other}/attachments", headers=admin).json() == []


def test_permissions_and_soft_delete(client, auth):
    pid = _patient(client, auth)
    assert _upload(client, auth, pid, role="nurse").status_code == 403                         # emr:write yo'q
    assert _upload(client, auth, pid, role="cashier").status_code == 403
    a = _upload(client, auth, pid).json()
    assert client.get(f"/patients/{pid}/attachments", headers=auth("cashier")).status_code == 403
    assert client.get(f"/attachments/{a['id']}/download", headers=auth("receptionist")).status_code == 403
    assert client.delete(f"/attachments/{a['id']}", headers=auth("nurse")).status_code == 403
    assert client.delete(f"/attachments/{a['id']}", headers=auth("doctor")).status_code == 200
    assert client.get(f"/attachments/{a['id']}/download", headers=auth("doctor")).status_code == 404
    assert client.get(f"/patients/{pid}/attachments", headers=auth("doctor")).json() == []
    from sqlalchemy import text

    from app.db.session import SessionLocal
    with SessionLocal() as db:                                                                  # yozuv va fayl saqlanib qoladi
        row = db.execute(text("select deleted_at is not null, storage_key from attachments where id = :i"), {"i": a["id"]}).one()
    assert row[0] is True
    from app.services.storage import get_storage
    assert get_storage().exists(row[1])
    assert client.post("/patients/00000000-0000-0000-0000-000000000000/attachments", headers=auth("doctor"),
                       files={"file": ("a.pdf", io.BytesIO(PDF))}).status_code == 404


def test_storage_key_cannot_escape_root():
    import pytest

    from app.services.storage import LocalStorage

    store = LocalStorage("/tmp/clinic-storage-test")
    with pytest.raises(ValueError):
        store.save("../../etc/passwd", b"x")
    store.save("abcdef.pdf", b"hello")
    assert b"".join(store.open("abcdef.pdf")) == b"hello" and store.exists("abcdef.pdf") and not store.exists("zzz.pdf")
