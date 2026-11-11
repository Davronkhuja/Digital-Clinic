"""2-bosqich "Shart"i: bitta qabul yozilishdan retseptgacha qog'ozsiz o'tadi.

Butun zanjir HTTP API orqali, rollar bo'yicha: qabulxona bemorni topadi/qo'shadi va bo'sh vaqtga yozadi; hamshira
laboratoriya natijasini kiritadi; shifokor ko'rik yozadi (shablon, MKB-10, INN retsept) va DMED kartasini oladi.
Har qadam auditga tushadi.
"""
import io
from datetime import date, timedelta

from pypdf import PdfReader

DOCTOR = "Dr. Behruz Rustamov"  # demo: Du-Ju 09:00-17:00, tanaffus 13:00-14:00, 101-kabinet


def _next_monday() -> str:
    d = date.today() + timedelta(days=14)
    return (d + timedelta(days=(0 - d.weekday()) % 7)).isoformat()


def test_paperless_flow_from_booking_to_prescription(client, auth):
    reception, doctor, nurse, admin = auth("receptionist"), auth("doctor"), auth("nurse"), auth("admin")
    day = _next_monday()

    # 1. Qabulxona: bemor topilmaydi -> yangi bemor (PINFL, telefon). Dublikat ro'yxatida yo'q.
    assert client.get("/patients", params={"search": "99 876 54 32"}, headers=reception).json() == []
    patient = client.post("/patients", headers=reception, json={
        "name": "Абдуллаев Ўктам", "phone": "+998 99 876 54 32", "birth_date": "1980-03-12", "gender": "male",
        "pinfl": "31203800000017", "address": "Toshkent, Chilonzor"})
    assert patient.status_code == 201
    pid = patient.json()["id"]
    assert client.get("/patients", params={"search": "998998765432"}, headers=reception).json()[0]["id"] == pid   # telefon raqamlari
    assert client.get("/patients", params={"search": "abdullayev"}, headers=reception).json()[0]["id"] == pid     # kirill/lotin
    assert all(pid not in {p["id"] for p in g["patients"]} for g in client.get("/patients/duplicates", headers=reception).json())

    # 2. Bo'sh vaqt: ish jadvali, tanaffus va band vaqtlar hisobga olingan
    doctor_id = next(s["id"] for s in client.get("/staff", headers=reception).json() if s["name"] == DOCTOR)
    slots = client.get(f"/staff/{doctor_id}/slots", params={"date": day, "type": "Konsultatsiya", "step_min": 30}, headers=reception).json()
    times = [s["time"] for s in slots["slots"]]
    assert times[0] == "09:00" and "13:00" not in times and slots["room_id"]
    chosen = times[2]                                                    # 10:00

    # 3. Yozish: tur bo'yicha davomiylik, shifokorning kabineti; shu vaqtga ikkinchi yozish mumkin emas
    appt = client.post("/appointments", headers=reception, json={
        "patient_id": pid, "doctor_id": doctor_id, "date": day, "time": chosen, "type": "Konsultatsiya"})
    assert appt.status_code == 201
    appt = appt.json()
    assert (appt["time"], appt["end_time"], appt["duration_min"], appt["room"]) == ("10:00", "10:30", 30, "101")
    other = client.post("/patients", headers=reception, json={"name": "Boshqa Bemor", "phone": "+998 90 000 00 00", "age": 40,
                                                              "gender": "female"}).json()["id"]
    assert client.post("/appointments", headers=reception, json={
        "patient_id": other, "doctor_id": doctor_id, "date": day, "time": chosen, "type": "Konsultatsiya"}).status_code == 409
    assert chosen not in [s["time"] for s in client.get(f"/staff/{doctor_id}/slots", params={"date": day, "step_min": 30},
                                                        headers=reception).json()["slots"]]

    # 4. Shifokor: shablon asosida ko'rik, MKB-10 bilan, qabulga bog'langan
    template = next(t for t in client.get("/emr-templates", headers=doctor).json() if t["name"].startswith("Umumiy"))
    icd = client.get("/icd10", params={"search": "gipertenziya"}, headers=doctor).json()[0]
    assert icd["code"] == "I10"
    enc = client.post("/emr", headers=doctor, json={
        "patient_id": pid, "doctor_id": doctor_id, "appointment_id": appt["id"], "visit_date": day, "icd_code": icd["code"],
        "diagnosis": icd["name_uz"], "prescription": "-", "complaints": "Bosh og'rig'i, bosh aylanishi",
        "anamnesis": template["anamnesis"], "examination": "AQB 150/95, puls 78", "recommendations": "Tuz kamaytirish"})
    assert enc.status_code == 201
    enc = enc.json()
    after = client.get("/appointments", params={"patient_id": pid}, headers=reception).json()[0]
    assert after["id"] == appt["id"] and after["status"] == "Completed"           # qabul avtomatik yakunlandi

    # 5. Laboratoriya: buyurtma ko'rikka bog'langan, hamshira natija kiritadi, me'yor bilan solishtiriladi
    panel = next(p for p in client.get("/lab/panels", headers=doctor).json() if p["name"].startswith("Lipid"))
    order = client.post("/lab/orders", headers=doctor, json={"patient_id": pid, "doctor_id": doctor_id, "encounter_id": enc["id"],
                                                            "panel_ids": [panel["id"]]}).json()
    values = {"CHOL": 6.4, "LDL": 3.9, "HDL": 1.3, "TG": 1.2}
    done = client.put(f"/lab/orders/{order['id']}/results", headers=nurse, json={
        "results": [{"item_id": i["id"], "value": values[i["code"]]} for i in order["items"]]}).json()
    assert done["status"] == "Completed"
    assert {i["code"]: i["flag"] for i in done["items"]} == {"CHOL": "High", "LDL": "High", "HDL": "Normal", "TG": "Normal"}

    # 6. Retsept: INN, doza, usul, muddat (tuzilgan)
    rx = client.post(f"/emr/{enc['id']}/prescriptions", headers=doctor, json={
        "inn": "Amlodipine", "dose": "5 mg", "route": "Oral", "frequency": "kuniga 1 marta", "duration_days": 30,
        "instructions": "Ertalab"})
    assert rx.status_code == 201 and rx.json()["inn"] == "amlodipine"
    assert client.post(f"/emr/{enc['id']}/prescriptions", headers=doctor, json={
        "inn": "atorvastatin", "dose": "20 mg", "route": "Oral", "frequency": "kechqurun", "duration_days": 90}).status_code == 201

    # 7. Ko'rik kartasi (DMED tartibida): hammasi bitta joyda, nusxalash uchun tayyor
    card = client.get(f"/emr/{enc['id']}/card", headers=doctor).json()
    sections = {f["key"]: f["value"] for f in card["sections"]}
    assert sections["complaints"].startswith("Bosh og'rig'i") and sections["examination"].startswith("AQB 150/95")
    assert card["icd_code"] == "I10" and "gipertenziya" in card["icd_name"].lower()
    assert [p["text"] for p in card["prescriptions"]] == [
        "amlodipine 5 mg, ichga, kuniga 1 marta, 30 kun", "atorvastatin 20 mg, ichga, kechqurun, 90 kun"]
    assert {r["name"]: r["flag"] for r in card["lab_results"]}["Umumiy xolesterin"] == "High"
    assert {f["key"]: f["value"] for f in card["patient"]}["pinfl"] == "31203800000017"

    # 8. Chop etish (PDF) va qo'lda "DMED ga ko'chirildi" belgisi
    pdf = client.get(f"/emr/{enc['id']}/card/pdf", headers=doctor)
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert pdf.status_code == 200 and "Абдуллаев" in text and "amlodipine" in text and "I10" in text
    marked = client.post(f"/emr/{enc['id']}/dmed-mark", headers=doctor, json={"copied": True}).json()
    assert marked["dmed_copied_at"] and marked["dmed_copied_by"] == DOCTOR

    # 9. Audit: butun zanjir izlanadi (bemor, ko'rik, retsept, laboratoriya)
    def actions(entity):
        items = client.get("/security/audit", params={"entity_type": entity, "limit": 200}, headers=admin).json()["items"]
        return {e["action"] for e in items}

    assert {"create"} <= actions("patient") and {"create", "update", "read"} <= actions("emr")
    assert {"create"} <= actions("prescription") and {"create", "update"} <= actions("lab_order")
