import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Appointment, Encounter, ExamTemplate, InnDrug, Prescription
from app.schemas import (
    EMRCreate,
    EMRRecord,
    EMRUpdate,
    ExamTemplateIn,
    ExamTemplateOut,
    ExamTemplateUpdate,
    InnIn,
    InnOut,
    PrescriptionIn,
    PrescriptionOut,
)
from app.schemas.enums import AppointmentStatus
from app.services import audit, icd10, inn, queries
from app.services import serializers as ser
from app.services.lookup import get_patient_or_404, resolve_doctor

router = APIRouter()


@router.get("/emr", tags=["📋 EMR"], response_model=List[EMRRecord], summary="Tibbiy yozuvlar ro'yxati")
def get_emr(request: Request, patient_id: Optional[uuid.UUID] = Query(None), db: Session = Depends(get_db),
            user: CurrentUser = Depends(require("emr:read"))):
    result = queries.list_encounters(db, patient_id)
    audit.record_read(db, user, request, "emr", details={"patient_id": str(patient_id) if patient_id else None, "count": len(result)})
    return result


@router.post("/emr", tags=["📋 EMR"], response_model=EMRRecord, status_code=201,
             summary="Yangi tibbiy yozuv qo'shish")
def create_emr(data: EMRCreate, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = resolve_doctor(db, data.doctor_id, data.doctor)
    try:
        visit_date = date.fromisoformat(data.visit_date)
    except ValueError:
        raise HTTPException(422, "visit_date noto'g'ri")
    icd_code = icd10.normalize_code(data.icd_code) if data.icd_code else None
    if icd_code and (not icd10.CODE_RE.match(icd_code) or not icd10.code_known(db, icd_code)):
        raise HTTPException(422, f"MKB-10 kodi topilmadi: {data.icd_code}")
    appt = None
    if data.appointment_id:
        appt = db.get(Appointment, data.appointment_id)
        if not appt or appt.patient_id != patient.id:
            raise HTTPException(422, "Qabul topilmadi yoki boshqa bemorga tegishli")
        if appt.status in (AppointmentStatus.cancelled, AppointmentStatus.no_show):
            raise HTTPException(409, "Bekor qilingan yoki kelmagan qabulga ko'rik yozib bo'lmaydi")
    enc = Encounter(patient_id=patient.id, doctor_id=doctor.id, visit_date=visit_date, icd_code=icd_code,
                    diagnosis=data.diagnosis, notes=data.notes, complaints=data.complaints, anamnesis=data.anamnesis,
                    examination=data.examination, recommendations=data.recommendations,
                    appointment_id=appt.id if appt else None, branch_id=user.branch_id, created_by=user.id)
    if appt:
        appt.status = AppointmentStatus.completed  # qabul -> ko'rik: qog'ozsiz zanjirning bir bo'g'ini
    db.add(enc)
    db.flush()
    if data.prescription.strip() and data.prescription.strip() != "-":
        db.add(Prescription(encounter_id=enc.id, patient_id=patient.id, medication=data.prescription.strip(),
                            branch_id=user.branch_id, created_by=user.id))
    audit.record(db, user, request, "create", "emr", enc.id, {"patient_id": str(patient.id)})
    db.commit()
    return queries.list_encounters(db, record_id=enc.id)[0]


@router.get("/emr/{record_id}", tags=["📋 EMR"], response_model=EMRRecord, summary="Bitta tibbiy yozuv")
def get_emr_record(record_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("emr:read"))):
    rows = queries.list_encounters(db, record_id=record_id)
    if not rows:
        raise HTTPException(404, "Yozuv topilmadi")
    audit.record_read(db, user, request, "emr", record_id, {"patient_id": rows[0]["patient_id"]})
    return rows[0]


def _template_out(t: ExamTemplate) -> dict:
    return {"id": str(t.id), "name": t.name, "specialty": t.specialty, "complaints": t.complaints,
            "anamnesis": t.anamnesis, "examination": t.examination, "diagnosis": t.diagnosis,
            "recommendations": t.recommendations, "is_active": t.is_active}


@router.get("/emr-templates", tags=["📋 EMR"], response_model=List[ExamTemplateOut], summary="Ko'rik shablonlari")
def get_templates(include_inactive: bool = False, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("emr:read"))):
    stmt = select(ExamTemplate).order_by(ExamTemplate.name)
    if not include_inactive:
        stmt = stmt.where(ExamTemplate.is_active.is_(True))
    return [_template_out(t) for t in db.scalars(stmt)]


@router.post("/emr-templates", tags=["📋 EMR"], response_model=ExamTemplateOut, status_code=201,
             summary="Ko'rik shabloni qo'shish")
def create_template(data: ExamTemplateIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:write"))):
    t = ExamTemplate(**{**data.model_dump(), "name": data.name.strip()}, created_by=user.id)
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli shablon allaqachon mavjud")
    return _template_out(t)


@router.put("/emr-templates/{template_id}", tags=["📋 EMR"], response_model=ExamTemplateOut,
            summary="Ko'rik shablonini o'zgartirish", description="Yozilgan ko'riklarga ta'sir qilmaydi (matn nusxalanadi).")
def update_template(template_id: uuid.UUID, data: ExamTemplateUpdate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("emr:write"))):
    t = db.get(ExamTemplate, template_id)
    if not t:
        raise HTTPException(404, "Shablon topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ("name", "is_active") and value is None:
            continue
        setattr(t, key, value.strip() if key == "name" else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli shablon allaqachon mavjud")
    return _template_out(t)


@router.delete("/emr-templates/{template_id}", tags=["📋 EMR"], summary="Ko'rik shablonini o'chirish",
               description="Shablon faqat andoza; yozilgan ko'riklar unga bog'liq emas.")
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:write"))):
    t = db.get(ExamTemplate, template_id)
    if not t:
        raise HTTPException(404, "Shablon topilmadi")
    db.delete(t)
    db.commit()
    return {"message": "Shablon o'chirildi"}


@router.put("/emr/{record_id}", tags=["📋 EMR"], response_model=EMRRecord, summary="Ko'rikni tahrirlash",
            description="Ko'rik o'chirilmaydi, faqat tahrirlanadi (audit: update).")
def update_emr(record_id: uuid.UUID, data: EMRUpdate, request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require("emr:write"))):
    enc = db.scalar(select(Encounter).where(Encounter.id == record_id, Encounter.deleted_at.is_(None)))
    if not enc:
        raise HTTPException(404, "Yozuv topilmadi")
    fields = data.model_dump(exclude_unset=True)
    if "icd_code" in fields:
        code = icd10.normalize_code(fields["icd_code"]) if fields["icd_code"] else None
        if code and (not icd10.CODE_RE.match(code) or not icd10.code_known(db, code)):
            raise HTTPException(422, f"MKB-10 kodi topilmadi: {fields['icd_code']}")
        enc.icd_code = code
        fields.pop("icd_code")
    for key, value in fields.items():
        if key == "diagnosis" and not value:
            continue
        setattr(enc, key, value)
    changed = sorted(data.model_dump(exclude_unset=True))
    audit.record(db, user, request, "update", "emr", enc.id, {"patient_id": str(enc.patient_id), "fields": changed})
    db.commit()
    return queries.list_encounters(db, record_id=enc.id)[0]


def _live_encounter(db: Session, record_id: uuid.UUID) -> Encounter:
    enc = db.scalar(select(Encounter).where(Encounter.id == record_id, Encounter.deleted_at.is_(None)))
    if not enc:
        raise HTTPException(404, "Yozuv topilmadi")
    return enc


@router.get("/emr/{record_id}/prescriptions", tags=["💊 Prescriptions"], response_model=List[PrescriptionOut],
            summary="Ko'rik retseptlari")
def get_prescriptions(record_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require("emr:read"))):
    enc = _live_encounter(db, record_id)
    rows = db.scalars(select(Prescription).where(Prescription.encounter_id == enc.id, Prescription.deleted_at.is_(None))
                      .order_by(Prescription.created_at)).all()
    audit.record_read(db, user, request, "emr", enc.id, {"patient_id": str(enc.patient_id), "prescriptions": len(rows)})
    return [ser.prescription_out(p) for p in rows]


@router.post("/emr/{record_id}/prescriptions", tags=["💊 Prescriptions"], response_model=PrescriptionOut, status_code=201,
             summary="INN bo'yicha retsept qo'shish",
             description="`inn` INN ma'lumotnomasida bo'lishi shart (422). Doza, yuborish usuli, chastota va muddat tuzilgan.")
def add_prescription(record_id: uuid.UUID, data: PrescriptionIn, request: Request, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require("emr:write"))):
    enc = _live_encounter(db, record_id)
    drug = inn.canonical(db, data.inn)
    if not drug:
        raise HTTPException(422, f"INN ro'yxatida yo'q: {data.inn}")
    p = Prescription(
        encounter_id=enc.id, patient_id=enc.patient_id, inn=drug.inn, dosage=data.dose.strip(), route=data.route,
        frequency=data.frequency.strip(), duration_days=data.duration_days, instructions=data.instructions,
        medication=ser.prescription_summary(drug.inn, data.dose.strip(), data.route, data.frequency.strip(), data.duration_days),
        branch_id=user.branch_id, created_by=user.id,
    )
    db.add(p)
    db.flush()
    audit.record(db, user, request, "create", "prescription", p.id, {"patient_id": str(enc.patient_id), "inn": drug.inn})
    db.commit()
    return ser.prescription_out(p)


@router.delete("/prescriptions/{prescription_id}", tags=["💊 Prescriptions"],
               summary="Retseptni bekor qilish (o'chirilmaydi, deleted_at)")
def cancel_prescription(prescription_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(require("emr:write"))):
    p = db.scalar(select(Prescription).where(Prescription.id == prescription_id, Prescription.deleted_at.is_(None)))
    if not p:
        raise HTTPException(404, "Retsept topilmadi")
    p.deleted_at = func.now()
    audit.record(db, user, request, "delete", "prescription", p.id, {"patient_id": str(p.patient_id), "inn": p.inn})
    db.commit()
    return {"message": "Retsept bekor qilindi"}


@router.get("/inn", tags=["💊 Prescriptions"], response_model=List[InnOut], summary="INN qidiruvi",
            description="Nom boshi, so'z boshi yoki farmakologik guruh bo'yicha.")
def search_inn(search: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
               user: CurrentUser = Depends(require("emr:read"))):
    return [{"inn": d.inn, "group_uz": d.group_uz} for d in inn.search(db, search, limit)]


@router.post("/inn", tags=["💊 Prescriptions"], response_model=InnOut, status_code=201, summary="INN qo'shish")
def add_inn(data: InnIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    name = " ".join(data.inn.split())
    if inn.canonical(db, name):
        raise HTTPException(409, "Bu INN allaqachon mavjud")
    drug = InnDrug(inn=name, group_uz=data.group_uz, created_by=user.id)
    db.add(drug)
    db.commit()
    return {"inn": drug.inn, "group_uz": drug.group_uz}
