import hashlib
import uuid
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Attachment, Encounter, Staff, User
from app.schemas.emr import AttachmentOut
from app.services import attachments as att
from app.services import audit
from app.services.lookup import get_patient_or_404
from app.services.periods import CLINIC_TZ
from app.services.storage import get_storage

router = APIRouter()
TAG = "📎 Attachments"


def _out(a: Attachment, uploader: str | None) -> dict:
    return {"id": str(a.id), "patient_id": str(a.patient_id), "encounter_id": str(a.encounter_id) if a.encounter_id else None,
            "filename": a.filename, "content_type": a.content_type, "size_bytes": a.size_bytes, "note": a.note,
            "uploaded_by": uploader, "created_at": a.created_at.astimezone(CLINIC_TZ).isoformat()}


def _rows(db: Session, *conditions) -> list[dict]:
    stmt = (select(Attachment, Staff.full_name).outerjoin(User, User.id == Attachment.created_by)
            .outerjoin(Staff, Staff.id == User.staff_id).where(Attachment.deleted_at.is_(None), *conditions)
            .order_by(Attachment.created_at.desc()))
    return [_out(a, name) for a, name in db.execute(stmt).all()]


@router.post("/patients/{patient_id}/attachments", tags=[TAG], response_model=AttachmentOut, status_code=201,
             summary="Faylni bemor kartasiga yoki ko'rikka biriktirish",
             description="PDF, JPG, PNG, DICOM; hajm `MAX_UPLOAD_MB` (standart 20). Tur baytlar bo'yicha aniqlanadi. "
                         "`encounter_id` berilsa, ko'rik shu bemorniki bo'lishi shart.")
def upload_attachment(patient_id: uuid.UUID, request: Request, file: UploadFile = File(...), encounter_id: Optional[uuid.UUID] = Form(None),
                      note: Optional[str] = Form(None), db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:write"))):
    patient = get_patient_or_404(db, patient_id)
    if encounter_id:
        enc = db.get(Encounter, encounter_id)
        if not enc or enc.deleted_at is not None or enc.patient_id != patient.id:
            raise HTTPException(422, "Ko'rik topilmadi yoki boshqa bemorga tegishli")
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Fayl {settings.max_upload_mb} MB dan katta")
    if not data:
        raise HTTPException(422, "Fayl bo'sh")
    detected = att.detect(data)
    if not detected:
        raise HTTPException(415, f"Fayl turi qo'llab-quvvatlanmaydi (ruxsat: {att.ALLOWED_LABEL})")
    key = f"{uuid.uuid4().hex}.{detected.ext}"
    get_storage().save(key, data)
    record = Attachment(patient_id=patient.id, encounter_id=encounter_id, filename=att.safe_filename(file.filename, detected.ext),
                        content_type=detected.content_type, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                        storage_key=key, note=(note or None) and note[:300], branch_id=user.branch_id, created_by=user.id)
    db.add(record)
    db.flush()
    audit.record(db, user, request, "create", "attachment", record.id,
                 {"patient_id": str(patient.id), "encounter_id": str(encounter_id) if encounter_id else None,
                  "filename": record.filename, "size": record.size_bytes})
    db.commit()
    return _rows(db, Attachment.id == record.id)[0]


@router.get("/patients/{patient_id}/attachments", tags=[TAG], response_model=List[AttachmentOut], summary="Bemor ilovalari")
def list_attachments(patient_id: uuid.UUID, request: Request, encounter_id: Optional[uuid.UUID] = Query(None),
                     db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:read"))):
    get_patient_or_404(db, patient_id)
    conditions = [Attachment.patient_id == patient_id]
    if encounter_id:
        conditions.append(Attachment.encounter_id == encounter_id)
    result = _rows(db, *conditions)
    audit.record_read(db, user, request, "attachment", details={"patient_id": str(patient_id), "count": len(result)})
    return result


def _live(db: Session, attachment_id: uuid.UUID) -> Attachment:
    a = db.scalar(select(Attachment).where(Attachment.id == attachment_id, Attachment.deleted_at.is_(None)))
    if not a:
        raise HTTPException(404, "Fayl topilmadi")
    return a


@router.get("/attachments/{attachment_id}/download", tags=[TAG], summary="Faylni yuklab olish (ruxsat bilan, auditga yoziladi)")
def download_attachment(attachment_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(require("emr:read"))):
    a = _live(db, attachment_id)
    storage = get_storage()
    if not storage.exists(a.storage_key):
        raise HTTPException(410, "Fayl saqlashda topilmadi")
    audit.record_read(db, user, request, "attachment", a.id, {"patient_id": str(a.patient_id), "filename": a.filename, "download": True})
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(a.filename)}",
        "Content-Length": str(a.size_bytes),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    return StreamingResponse(storage.open(a.storage_key), media_type=a.content_type, headers=headers)


@router.delete("/attachments/{attachment_id}", tags=[TAG], summary="Faylni olib tashlash (yozuv `deleted_at`, fayl saqlashda qoladi)")
def delete_attachment(attachment_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require("emr:write"))):
    a = _live(db, attachment_id)
    a.deleted_at = func.now()
    audit.record(db, user, request, "delete", "attachment", a.id, {"patient_id": str(a.patient_id), "filename": a.filename})
    db.commit()
    return {"message": "Fayl olib tashlandi"}
