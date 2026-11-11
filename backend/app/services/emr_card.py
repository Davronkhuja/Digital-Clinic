"""Ko'rik kartasi (DMED ko'rik kartasi maydonlari tartibida). DMED bilan API integratsiyasi yo'q: shifokor/qabulxona
maydonlarni nusxalab, DMED ga qo'lda kiritadi va "ko'chirildi" belgisini qo'yadi."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Encounter, Icd10Code, LabOrder, LabOrderItem, Patient, Prescription, Staff, User
from app.services import serializers as ser

GENDER_UZ = {"male": "Erkak", "female": "Ayol", "other": "Boshqa"}


def build_card(db: Session, enc: Encounter) -> dict:
    patient = db.get(Patient, enc.patient_id)
    doctor = db.get(Staff, enc.doctor_id)
    icd_name = None
    if enc.icd_code:
        row = db.scalar(select(Icd10Code).where(Icd10Code.code.in_({enc.icd_code, enc.icd_code.split(".")[0]}))
                        .order_by(Icd10Code.code.desc()))
        icd_name = row.name_uz if row else None
    rx = db.scalars(select(Prescription).where(Prescription.encounter_id == enc.id, Prescription.deleted_at.is_(None),
                                               Prescription.inn.is_not(None)).order_by(Prescription.created_at)).all()
    labs = db.execute(
        select(LabOrderItem).join(LabOrder, LabOrderItem.order_id == LabOrder.id)
        .where(LabOrder.encounter_id == enc.id, LabOrderItem.value.is_not(None)).order_by(LabOrder.created_at, LabOrderItem.position)
    ).scalars().all()
    copied_by = None
    if enc.dmed_copied_by:
        user = db.get(User, enc.dmed_copied_by)
        copied_by = db.get(Staff, user.staff_id).full_name if user else None

    def field(key, label, value):
        return {"key": key, "label": label, "value": str(value) if value not in (None, "") else None}

    return {
        "record_id": str(enc.id),
        "patient": [
            field("full_name", "F.I.Sh.", patient.full_name), field("birth_date", "Tug'ilgan sana", patient.birth_date),
            field("gender", "Jinsi", GENDER_UZ.get(patient.gender.value)), field("pinfl", "PINFL", patient.pinfl),
            field("phone", "Telefon", patient.phone), field("address", "Manzil", patient.address),
        ],
        "visit": [field("visit_date", "Murojaat sanasi", enc.visit_date), field("doctor", "Shifokor", doctor.full_name)],
        "sections": [
            field("complaints", "Shikoyatlar", enc.complaints), field("anamnesis", "Anamnez", enc.anamnesis),
            field("examination", "Ob'ektiv ko'rik", enc.examination), field("diagnosis", "Tashxis", enc.diagnosis),
            field("recommendations", "Tavsiyalar", enc.recommendations),
        ],
        "icd_code": enc.icd_code, "icd_name": icd_name,
        "prescriptions": [
            {"inn": p.inn, "dose": p.dosage, "route": ser.ROUTE_UZ.get(p.route.value) if p.route else None,
             "frequency": p.frequency, "duration_days": p.duration_days, "instructions": p.instructions, "text": p.medication}
            for p in rx
        ],
        "lab_results": [
            {"name": i.test_name, "value": float(i.value), "unit": i.unit, "flag": i.flag.value if i.flag else None,
             "reference": _reference(i)} for i in labs
        ],
        "dmed_copied_at": enc.dmed_copied_at.isoformat() if enc.dmed_copied_at else None,
        "dmed_copied_by": copied_by,
    }


def _reference(item: LabOrderItem) -> str | None:
    low, high = item.ref_low, item.ref_high
    fmt = lambda v: format(v.normalize(), "f")  # noqa: E731
    if low is not None and high is not None:
        return f"{fmt(low)} - {fmt(high)}"
    if high is not None:
        return f"<= {fmt(high)}"
    return f">= {fmt(low)}" if low is not None else None
