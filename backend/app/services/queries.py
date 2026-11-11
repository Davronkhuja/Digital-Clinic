"""Ro'yxat so'rovlari: routerlar va hisobotlar uchun umumiy (join orqali nomlar)."""
import re
import uuid
from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Appointment, Encounter, Patient, Prescription, Staff, Transaction
from app.schemas.enums import AppointmentStatus, StaffRole, StatusEnum, TransactionType
from app.services import serializers as ser


def _parse_date(text: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _digits(column):
    return func.regexp_replace(column, "[^0-9]", "", "g")


def patient_search_clause(search: str):
    """Ism, telefon (faqat raqamlar bo'yicha), PINFL va tug'ilgan sana (YYYY-MM-DD, DD.MM.YYYY)."""
    text = search.strip()
    conds = [Patient.full_name.ilike(f"%{text}%"), Patient.pinfl.ilike(f"%{text}%")]
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 3 and re.fullmatch(r"[\d\s+()\-]+", text):
        conds.append(_digits(Patient.phone).like(f"%{digits}%"))
    else:
        conds.append(Patient.phone.ilike(f"%{text}%"))
    born = _parse_date(text)
    if born:
        conds.append(Patient.birth_date == born)
    return or_(*conds)


def list_patients(
    db: Session, search: str | None = None, status: StatusEnum | None = None, skip: int = 0, limit: int = 100
) -> list[dict]:
    last_visit = (
        select(Appointment.patient_id, func.max(Appointment.date).label("lv"))
        .where(Appointment.status == AppointmentStatus.completed)
        .group_by(Appointment.patient_id)
        .subquery()
    )
    stmt = (
        select(Patient, Staff.full_name, last_visit.c.lv)
        .outerjoin(Staff, Patient.primary_doctor_id == Staff.id)
        .outerjoin(last_visit, last_visit.c.patient_id == Patient.id)
        .order_by(Patient.created_at, Patient.id)
    )
    if search:
        stmt = stmt.where(patient_search_clause(search))
    if status:
        stmt = stmt.where(Patient.status == status)
    rows = db.execute(stmt.offset(skip).limit(limit)).all()
    return [ser.patient_out(p, doctor, lv) for p, doctor, lv in rows]


def get_patient(db: Session, patient_id: uuid.UUID) -> dict | None:
    last_visit = db.scalar(
        select(func.max(Appointment.date)).where(
            Appointment.patient_id == patient_id, Appointment.status == AppointmentStatus.completed
        )
    )
    row = db.execute(
        select(Patient, Staff.full_name)
        .outerjoin(Staff, Patient.primary_doctor_id == Staff.id)
        .where(Patient.id == patient_id)
    ).first()
    return ser.patient_out(row[0], row[1], last_visit) if row else None


def list_appointments(
    db: Session,
    date_: str | None = None,
    doctor: str | None = None,
    status: AppointmentStatus | None = None,
    patient_id: uuid.UUID | None = None,
    appt_id: uuid.UUID | None = None,
) -> list[dict]:
    stmt = (
        select(Appointment, Patient.full_name, Staff.full_name)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Staff, Appointment.doctor_id == Staff.id)
        .order_by(Appointment.date, Appointment.time, Appointment.id)
    )
    if date_:
        stmt = stmt.where(Appointment.date == date.fromisoformat(date_))
    if doctor:
        stmt = stmt.where(Staff.full_name.ilike(f"%{doctor}%"))
    if status:
        stmt = stmt.where(Appointment.status == status)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if appt_id:
        stmt = stmt.where(Appointment.id == appt_id)
    return [ser.appointment_out(a, pn, dn) for a, pn, dn in db.execute(stmt).all()]


def list_encounters(
    db: Session, patient_id: uuid.UUID | None = None, record_id: uuid.UUID | None = None
) -> list[dict]:
    rx = (
        select(Prescription.encounter_id, func.string_agg(Prescription.medication, "; ").label("rx"))
        .where(Prescription.deleted_at.is_(None))
        .group_by(Prescription.encounter_id)
        .subquery()
    )
    stmt = (
        select(Encounter, Patient.full_name, Staff.full_name, rx.c.rx)
        .join(Patient, Encounter.patient_id == Patient.id)
        .join(Staff, Encounter.doctor_id == Staff.id)
        .outerjoin(rx, rx.c.encounter_id == Encounter.id)
        .where(Encounter.deleted_at.is_(None))
        .order_by(Encounter.visit_date.desc(), Encounter.created_at.desc())
    )
    if patient_id:
        stmt = stmt.where(Encounter.patient_id == patient_id)
    if record_id:
        stmt = stmt.where(Encounter.id == record_id)
    return [ser.encounter_out(e, pn, dn, r or "") for e, pn, dn, r in db.execute(stmt).all()]


def list_transactions(
    db: Session,
    type_: TransactionType | None = None,
    category: str | None = None,
    since: date | None = None,
) -> list[dict]:
    stmt = (
        select(Transaction, Patient.full_name)
        .outerjoin(Patient, Transaction.patient_id == Patient.id)
        .where(Transaction.deleted_at.is_(None))
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
    )
    if type_:
        stmt = stmt.where(Transaction.type == type_)
    if category:
        stmt = stmt.where(Transaction.category == category)
    if since:
        stmt = stmt.where(Transaction.date >= since)
    return [ser.transaction_out(t, pn) for t, pn in db.execute(stmt).all()]


def list_staff(db: Session, role: StaffRole | None = None, staff_id: uuid.UUID | None = None) -> list[dict]:
    counts = (
        select(Appointment.doctor_id, func.count(func.distinct(Appointment.patient_id)).label("n"))
        .group_by(Appointment.doctor_id)
        .subquery()
    )
    stmt = (
        select(Staff, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.doctor_id == Staff.id)
        .order_by(Staff.created_at, Staff.id)
    )
    if role:
        stmt = stmt.where(Staff.role == role)
    if staff_id:
        stmt = stmt.where(Staff.id == staff_id)
    return [ser.staff_out(s, n) for s, n in db.execute(stmt).all()]




def patient_duplicate_groups(db: Session) -> list[dict]:
    """Ehtimoliy dublikatlar: bir xil ism va (telefon raqamlari yoki tug'ilgan sana). Faqat faol bemorlar."""
    name = func.lower(func.trim(Patient.full_name))
    groups: dict[frozenset, dict] = {}
    for reason, key, empty in (("phone", _digits(Patient.phone), _digits(Patient.phone) == ""),
                               ("birth_date", Patient.birth_date, Patient.birth_date.is_(None))):
        dup_keys = (
            select(name.label("n"), key.label("k"))
            .where(Patient.status == StatusEnum.active, ~empty)
            .group_by(name, key)
            .having(func.count() > 1)
            .subquery()
        )
        rows = db.execute(
            select(Patient, dup_keys.c.n, dup_keys.c.k)
            .join(dup_keys, (name == dup_keys.c.n) & (key == dup_keys.c.k))
            .where(Patient.status == StatusEnum.active)
            .order_by(Patient.created_at, Patient.id)
        ).all()
        members: dict[tuple, list] = {}
        for p, n, k in rows:
            members.setdefault((n, k), []).append(p)
        for plist in members.values():
            ids = frozenset(p.id for p in plist)
            if ids in groups:
                groups[ids]["reasons"].append(reason)
            else:
                groups[ids] = {"reasons": [reason], "patients": [ser.patient_out(p, None, None) for p in plist]}
    return list(groups.values())
