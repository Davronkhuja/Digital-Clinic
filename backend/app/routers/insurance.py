# ruff: noqa: E501
import uuid
from decimal import Decimal
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import (
    GuaranteeLetter,
    GuaranteeLetterService,
    InsuranceContract,
    InsuranceContractService,
    Insurer,
    Patient,
    PatientPolicy,
    Service,
)
from app.schemas import (
    ContractIn,
    ContractOut,
    ContractUpdate,
    InsurerIn,
    InsurerOut,
    InsurerUpdate,
    LetterCancelIn,
    LetterIn,
    LetterOut,
    LetterUpdate,
    PolicyIn,
    PolicyOut,
    PolicyUpdate,
)
from app.services import attachments as att
from app.services import audit
from app.services import insurance as ins
from app.services.lookup import get_patient_or_404
from app.services.storage import get_storage

router = APIRouter()
TAG = "🛡 Insurance (sug'urta, DMS)"


def insurer_out(db: Session, i: Insurer) -> dict:
    n = db.scalar(select(func.count()).select_from(InsuranceContract).where(InsuranceContract.insurer_id == i.id))
    return {"id": str(i.id), "name": i.name, "tin": i.tin, "phone": i.phone, "email": i.email, "address": i.address, "contact_person": i.contact_person,
            "payment_days": i.payment_days, "is_active": i.is_active, "notes": i.notes, "contracts": n}


def contract_out(db: Session, c: InsuranceContract) -> dict:
    rows = db.execute(select(InsuranceContractService, Service.name).join(Service, InsuranceContractService.service_id == Service.id)
                      .where(InsuranceContractService.contract_id == c.id).order_by(Service.name)).all()
    return {"id": str(c.id), "insurer_id": str(c.insurer_id), "insurer": db.get(Insurer, c.insurer_id).name, "number": c.number, "valid_from": c.valid_from,
            "valid_to": c.valid_to, "discount_percent": c.discount_percent, "coverage_all": c.coverage_all, "default_coverage_percent": c.default_coverage_percent,
            "annual_limit": c.annual_limit, "per_visit_limit": c.per_visit_limit, "requires_guarantee": c.requires_guarantee, "is_active": c.is_active,
            "notes": c.notes, "services": [{"service_id": str(s.service_id), "service": name, "coverage_percent": s.coverage_percent} for s, name in rows]}


def _uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(422, f"{what} noto'g'ri")


# ---------- Kompaniyalar ----------

@router.get("/insurance/insurers", tags=[TAG], response_model=List[InsurerOut], summary="Sug'urta kompaniyalari")
def list_insurers(include_inactive: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    stmt = select(Insurer).order_by(Insurer.name)
    if not include_inactive:
        stmt = stmt.where(Insurer.is_active.is_(True))
    return [insurer_out(db, i) for i in db.scalars(stmt)]


@router.post("/insurance/insurers", tags=[TAG], response_model=InsurerOut, status_code=201, summary="Kompaniya qo'shish",
             description="Faqat ixtiyoriy tibbiy sug'urta (DMS); davlat jamg'armasi yo'q. `insurance:manage`. Nom registrsiz noyob; kompaniya o'chirilmaydi, faolsizlantiriladi.")
def create_insurer(data: InsurerIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    i = Insurer(**{**data.model_dump(), "name": data.name.strip()}, created_by=user.id)
    db.add(i)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli kompaniya allaqachon mavjud")
    audit.record(db, user, request, "create", "insurer", i.id, {"name": i.name})
    db.commit()
    return insurer_out(db, i)


@router.put("/insurance/insurers/{insurer_id}", tags=[TAG], response_model=InsurerOut, summary="Kompaniyani o'zgartirish")
def update_insurer(insurer_id: uuid.UUID, data: InsurerUpdate, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    i = db.get(Insurer, insurer_id)
    if not i:
        raise HTTPException(404, "Kompaniya topilmadi")
    changes = {}
    for k, v in data.model_dump(exclude_unset=True).items():
        if k in ("name", "payment_days", "is_active") and v is None:
            continue
        v = v.strip() if isinstance(v, str) else v
        if getattr(i, k) != v:
            changes[k] = {"from": getattr(i, k), "to": v}
            setattr(i, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli kompaniya allaqachon mavjud")
    if changes:
        audit.record(db, user, request, "update", "insurer", i.id, {"changes": changes})
    db.commit()
    return insurer_out(db, i)


# ---------- Shartnomalar ----------

def _set_services(db: Session, contract: InsuranceContract, items, actor) -> None:
    ids = [_uuid(s.service_id, "service_id") for s in items]
    found = set(db.scalars(select(Service.id).where(Service.id.in_(ids))))
    if set(ids) - found:
        raise HTTPException(422, "Xizmat topilmadi")
    db.execute(delete(InsuranceContractService).where(InsuranceContractService.contract_id == contract.id))
    db.flush()
    for s, sid in zip(items, ids, strict=True):
        db.add(InsuranceContractService(contract_id=contract.id, service_id=sid, coverage_percent=s.coverage_percent, created_by=actor))


@router.get("/insurance/contracts", tags=[TAG], response_model=List[ContractOut], summary="Shartnomalar")
def list_contracts(insurer_id: Optional[uuid.UUID] = None, include_inactive: bool = False, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("insurance:read"))):
    stmt = select(InsuranceContract).order_by(InsuranceContract.valid_from.desc(), InsuranceContract.number)
    if insurer_id:
        stmt = stmt.where(InsuranceContract.insurer_id == insurer_id)
    if not include_inactive:
        stmt = stmt.where(InsuranceContract.is_active.is_(True))
    return [contract_out(db, c) for c in db.scalars(stmt)]


@router.get("/insurance/contracts/{contract_id}", tags=[TAG], response_model=ContractOut, summary="Bitta shartnoma")
def get_contract(contract_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    c = db.get(InsuranceContract, contract_id)
    if not c:
        raise HTTPException(404, "Shartnoma topilmadi")
    return contract_out(db, c)


@router.post("/insurance/contracts", tags=[TAG], response_model=ContractOut, status_code=201, summary="Shartnoma qo'shish",
             description="Muddat, klinika narxiga chegirma (%), qoplanadigan xizmatlar ro'yxati (yoki `coverage_all`) va qoplash foizi, limitlar (bemor uchun yillik va "
                         "bitta hisob-faktura bo'yicha sug'urta ulushi), kafolat xati talabi. Raqam kompaniya ichida noyob. `insurance:manage`.")
def create_contract(data: ContractIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    insurer = db.get(Insurer, _uuid(data.insurer_id, "insurer_id"))
    if not insurer or not insurer.is_active:
        raise HTTPException(422, "Kompaniya topilmadi yoki faol emas")
    c = InsuranceContract(insurer_id=insurer.id, number=data.number.strip(), valid_from=data.valid_from, valid_to=data.valid_to, discount_percent=data.discount_percent,
                          coverage_all=data.coverage_all, default_coverage_percent=data.default_coverage_percent, annual_limit=data.annual_limit,
                          per_visit_limit=data.per_visit_limit, requires_guarantee=data.requires_guarantee, is_active=data.is_active, notes=data.notes,
                          created_by=user.id)
    db.add(c)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniyada bunday raqamli shartnoma allaqachon mavjud")
    _set_services(db, c, data.services, user.id)
    audit.record(db, user, request, "create", "insurance_contract", c.id, {"insurer": insurer.name, "number": c.number, "services": len(data.services)})
    db.commit()
    return contract_out(db, c)


@router.put("/insurance/contracts/{contract_id}", tags=[TAG], response_model=ContractOut, summary="Shartnomani o'zgartirish",
            description="`services` berilsa qoplanadigan xizmatlar ro'yxati to'liq almashtiriladi. Yozilgan hisob-fakturalarga ta'sir qilmaydi.")
def update_contract(contract_id: uuid.UUID, data: ContractUpdate, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    c = db.get(InsuranceContract, contract_id)
    if not c:
        raise HTTPException(404, "Shartnoma topilmadi")
    fields = data.model_dump(exclude_unset=True)
    services = fields.pop("services", None)
    changes = {}
    for k, v in fields.items():
        if k in ("number", "valid_from", "discount_percent", "coverage_all", "default_coverage_percent", "requires_guarantee", "is_active") and v is None:
            continue
        v = v.strip() if isinstance(v, str) else v
        if getattr(c, k) != v:
            changes[k] = {"from": str(getattr(c, k)), "to": str(v)}
            setattr(c, k, v)
    if c.valid_to and c.valid_to < c.valid_from:
        raise HTTPException(422, "Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
    if services is not None:
        items = data.services
        if c.coverage_all and items:
            raise HTTPException(422, "coverage_all=true bo'lsa xizmatlar ro'yxati bo'sh bo'lishi kerak")
        if len({s.service_id for s in items}) != len(items):
            raise HTTPException(422, "Xizmat ro'yxatda takrorlangan")
        _set_services(db, c, items, user.id)
        changes["services"] = len(items)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniyada bunday raqamli shartnoma allaqachon mavjud")
    if changes:
        audit.record(db, user, request, "update", "insurance_contract", c.id, {"changes": changes})
    db.commit()
    return contract_out(db, c)


# ---------- Bemor polislari ----------

def policy_out(db: Session, p: PatientPolicy) -> dict:
    contract = db.get(InsuranceContract, p.contract_id)
    return {"id": str(p.id), "patient_id": str(p.patient_id), "patient": db.get(Patient, p.patient_id).full_name, "insurer_id": str(p.insurer_id),
            "insurer": db.get(Insurer, p.insurer_id).name, "contract_id": str(p.contract_id), "contract": contract.number, "number": p.number,
            "valid_from": p.valid_from, "valid_to": p.valid_to, "is_active": p.is_active, "valid_now": ins.policy_valid(p, contract),
            "discount_percent": contract.discount_percent, "requires_guarantee": contract.requires_guarantee, "notes": p.notes}


@router.get("/patients/{patient_id}/policies", tags=[TAG], response_model=List[PolicyOut], summary="Bemorning sug'urta polislari")
def patient_policies(patient_id: uuid.UUID, valid_only: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    get_patient_or_404(db, patient_id)
    rows = [policy_out(db, p) for p in db.scalars(select(PatientPolicy).where(PatientPolicy.patient_id == patient_id).order_by(PatientPolicy.valid_from.desc()))]
    return [r for r in rows if r["valid_now"]] if valid_only else rows


@router.post("/patients/{patient_id}/policies", tags=[TAG], response_model=PolicyOut, status_code=201, summary="Bemorga polis qo'shish",
             description="Shartnoma faol bo'lishi shart; polis raqami kompaniya ichida noyob. `insurance:write`.")
def create_policy(patient_id: uuid.UUID, data: PolicyIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:write"))):
    patient = get_patient_or_404(db, patient_id)
    contract = db.get(InsuranceContract, _uuid(data.contract_id, "contract_id"))
    if not contract or not contract.is_active:
        raise HTTPException(422, "Shartnoma topilmadi yoki faol emas")
    if not db.get(Insurer, contract.insurer_id).is_active:
        raise HTTPException(422, "Kompaniya faol emas")
    p = PatientPolicy(patient_id=patient.id, insurer_id=contract.insurer_id, contract_id=contract.id, number=data.number.strip(), valid_from=data.valid_from,
                      valid_to=data.valid_to, notes=data.notes, created_by=user.id)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniyada bunday raqamli polis allaqachon mavjud")
    audit.record(db, user, request, "create", "patient_policy", p.id, {"patient_id": str(patient.id), "insurer_id": str(p.insurer_id), "number": p.number})
    db.commit()
    return policy_out(db, p)


@router.get("/insurance/policies", tags=[TAG], response_model=List[PolicyOut], summary="Polislarni qidirish (raqam, kompaniya, bemor)")
def list_policies(number: Optional[str] = None, insurer_id: Optional[uuid.UUID] = None, patient_id: Optional[uuid.UUID] = None, valid_only: bool = False,
                  limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    stmt = select(PatientPolicy).order_by(PatientPolicy.created_at.desc()).limit(limit)
    if number:
        stmt = stmt.where(PatientPolicy.number.ilike(f"%{number.strip()}%"))
    if insurer_id:
        stmt = stmt.where(PatientPolicy.insurer_id == insurer_id)
    if patient_id:
        stmt = stmt.where(PatientPolicy.patient_id == patient_id)
    rows = [policy_out(db, p) for p in db.scalars(stmt)]
    return [r for r in rows if r["valid_now"]] if valid_only else rows


@router.put("/insurance/policies/{policy_id}", tags=[TAG], response_model=PolicyOut, summary="Polisni o'zgartirish (muddat, faollik)")
def update_policy(policy_id: uuid.UUID, data: PolicyUpdate, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:write"))):
    p = db.get(PatientPolicy, policy_id)
    if not p:
        raise HTTPException(404, "Polis topilmadi")
    changes = {}
    for k, v in data.model_dump(exclude_unset=True).items():
        if k in ("number", "valid_from", "is_active") and v is None:
            continue
        v = v.strip() if isinstance(v, str) else v
        if getattr(p, k) != v:
            changes[k] = {"from": str(getattr(p, k)), "to": str(v)}
            setattr(p, k, v)
    if p.valid_to and p.valid_to < p.valid_from:
        raise HTTPException(422, "Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniyada bunday raqamli polis allaqachon mavjud")
    if changes:
        audit.record(db, user, request, "update", "patient_policy", p.id, {"changes": changes})
    db.commit()
    return policy_out(db, p)


# ---------- Kafolat xatlari ----------

def letter_out(db: Session, g: GuaranteeLetter) -> dict:
    policy = db.get(PatientPolicy, g.policy_id)
    used = ins.letter_used(db, g.id)
    services = db.execute(select(GuaranteeLetterService.service_id, Service.name).join(Service, GuaranteeLetterService.service_id == Service.id)
                          .where(GuaranteeLetterService.letter_id == g.id).order_by(Service.name)).all()
    return {"id": str(g.id), "number": g.number, "insurer_id": str(g.insurer_id), "insurer": db.get(Insurer, g.insurer_id).name, "policy_id": str(g.policy_id),
            "policy_number": policy.number, "patient_id": str(policy.patient_id), "patient": db.get(Patient, policy.patient_id).full_name, "letter_date": g.letter_date,
            "amount_limit": g.amount_limit, "used_amount": used, "remaining": max(g.amount_limit - used, Decimal(0)), "valid_from": g.valid_from, "valid_to": g.valid_to,
            "status": g.status, "state": ins.letter_state(g, used), "cancel_reason": g.cancel_reason, "notes": g.notes,
            "services": [{"service_id": str(sid), "service": name} for sid, name in services], "has_file": g.file_key is not None, "file_name": g.file_name,
            "file_size": g.file_size}


def _letter_services(db: Session, g: GuaranteeLetter, service_ids: list[str], actor) -> None:
    ids = [_uuid(s, "service_ids") for s in service_ids]
    if set(ids) - set(db.scalars(select(Service.id).where(Service.id.in_(ids)))):
        raise HTTPException(422, "Xizmat topilmadi")
    db.execute(delete(GuaranteeLetterService).where(GuaranteeLetterService.letter_id == g.id))
    db.flush()
    for sid in ids:
        db.add(GuaranteeLetterService(letter_id=g.id, service_id=sid, created_by=actor))


def _letter(db: Session, letter_id: uuid.UUID) -> GuaranteeLetter:
    g = db.get(GuaranteeLetter, letter_id)
    if not g:
        raise HTTPException(404, "Kafolat xati topilmadi")
    return g


@router.post("/insurance/guarantee-letters", tags=[TAG], response_model=LetterOut, status_code=201, summary="Kafolat xatini kiritish",
             description="Polis (amal qilayotgan) bo'yicha: raqam (kompaniya ichida noyob), sana, summa limiti, muddat, qamrab olingan xizmatlar. Skan faylni "
                         "`POST /insurance/guarantee-letters/{id}/file` bilan biriktiring. `insurance:write`.")
def create_letter(data: LetterIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:write"))):
    policy = db.get(PatientPolicy, _uuid(data.policy_id, "policy_id"))
    if not policy:
        raise HTTPException(422, "Polis topilmadi")
    if not ins.policy_valid(policy, db.get(InsuranceContract, policy.contract_id)):
        raise HTTPException(422, "Polis yoki shartnoma amal qilmayapti (muddat yoki faollik)")
    g = GuaranteeLetter(insurer_id=policy.insurer_id, policy_id=policy.id, number=data.number.strip(), letter_date=data.letter_date, amount_limit=data.amount_limit,
                        valid_from=data.valid_from, valid_to=data.valid_to, notes=data.notes, created_by=user.id)
    db.add(g)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniyada bunday raqamli kafolat xati allaqachon mavjud")
    _letter_services(db, g, data.service_ids, user.id)
    audit.record(db, user, request, "create", "guarantee_letter", g.id, {"number": g.number, "policy": policy.number, "limit": str(g.amount_limit)})
    db.commit()
    return letter_out(db, g)


@router.get("/insurance/guarantee-letters", tags=[TAG], response_model=List[LetterOut], summary="Kafolat xatlari")
def list_letters(policy_id: Optional[uuid.UUID] = None, patient_id: Optional[uuid.UUID] = None, insurer_id: Optional[uuid.UUID] = None, number: Optional[str] = None,
                 state: Optional[str] = Query(None, pattern="^(Active|Expired|Exhausted|Cancelled)$"), limit: int = Query(50, ge=1, le=200),
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    stmt = select(GuaranteeLetter).order_by(GuaranteeLetter.letter_date.desc(), GuaranteeLetter.number).limit(limit)
    if policy_id:
        stmt = stmt.where(GuaranteeLetter.policy_id == policy_id)
    if patient_id:
        stmt = stmt.where(GuaranteeLetter.policy_id.in_(select(PatientPolicy.id).where(PatientPolicy.patient_id == patient_id)))
    if insurer_id:
        stmt = stmt.where(GuaranteeLetter.insurer_id == insurer_id)
    if number:
        stmt = stmt.where(GuaranteeLetter.number.ilike(f"%{number.strip()}%"))
    rows = [letter_out(db, g) for g in db.scalars(stmt)]
    return [r for r in rows if r["state"] == state] if state else rows


@router.get("/insurance/guarantee-letters/{letter_id}", tags=[TAG], response_model=LetterOut, summary="Bitta kafolat xati")
def get_letter(letter_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    return letter_out(db, _letter(db, letter_id))


@router.put("/insurance/guarantee-letters/{letter_id}", tags=[TAG], response_model=LetterOut, summary="Kafolat xatini o'zgartirish",
            description="Limit ishlatilgan summadan kam bo'lishi mumkin emas (422). Bekor qilingan xat o'zgarmaydi (409).")
def update_letter(letter_id: uuid.UUID, data: LetterUpdate, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:write"))):
    g = _letter(db, letter_id)
    if g.status == "Cancelled":
        raise HTTPException(409, "Bekor qilingan kafolat xati o'zgartirilmaydi")
    fields = data.model_dump(exclude_unset=True)
    service_ids = fields.pop("service_ids", None)
    changes = {}
    for k, v in fields.items():
        if k in ("number", "letter_date", "amount_limit") and v is None:
            continue
        v = v.strip() if isinstance(v, str) else v
        if getattr(g, k) != v:
            changes[k] = {"from": str(getattr(g, k)), "to": str(v)}
            setattr(g, k, v)
    if g.valid_from and g.valid_to and g.valid_to < g.valid_from:
        raise HTTPException(422, "Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
    if "amount_limit" in changes and g.amount_limit < ins.letter_used(db, g.id):
        raise HTTPException(422, "Limit ishlatilgan summadan kam bo'lishi mumkin emas")
    if service_ids is not None:
        _letter_services(db, g, service_ids, user.id)
        changes["services"] = len(service_ids)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniyada bunday raqamli kafolat xati allaqachon mavjud")
    if changes:
        audit.record(db, user, request, "update", "guarantee_letter", g.id, {"changes": changes})
    db.commit()
    return letter_out(db, g)


@router.post("/insurance/guarantee-letters/{letter_id}/cancel", tags=[TAG], response_model=LetterOut, summary="Kafolat xatini bekor qilish",
             description="Sabab majburiy. Allaqachon yozilgan hisob-fakturalar o'zgarmaydi; yangilariga bog'lab bo'lmaydi. O'chirilmaydi.")
def cancel_letter(letter_id: uuid.UUID, data: LetterCancelIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:write"))):
    g = _letter(db, letter_id)
    if g.status == "Cancelled":
        raise HTTPException(409, "Kafolat xati allaqachon bekor qilingan")
    g.status, g.cancel_reason = "Cancelled", data.reason.strip()
    audit.record(db, user, request, "update", "guarantee_letter", g.id, {"number": g.number, "status": "Cancelled", "reason": g.cancel_reason})
    db.commit()
    return letter_out(db, g)


@router.post("/insurance/guarantee-letters/{letter_id}/file", tags=[TAG], response_model=LetterOut, summary="Kafolat xati skanini biriktirish (PDF, JPG, PNG)",
             description="Hajm `MAX_UPLOAD_MB`. Tur baytlar bo'yicha aniqlanadi. Qayta yuklansa almashtiriladi. `insurance:write`.")
def upload_letter_file(letter_id: uuid.UUID, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("insurance:write"))):
    g = _letter(db, letter_id)
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Fayl {settings.max_upload_mb} MB dan katta")
    if not data:
        raise HTTPException(422, "Fayl bo'sh")
    detected = att.detect(data)
    if not detected or detected.ext not in ("pdf", "jpg", "png"):
        raise HTTPException(415, "Fayl turi qo'llab-quvvatlanmaydi (ruxsat: PDF, JPG, PNG)")
    key = f"{uuid.uuid4().hex}.{detected.ext}"
    get_storage().save(key, data)
    g.file_key, g.file_name, g.file_type, g.file_size = key, att.safe_filename(file.filename, detected.ext), detected.content_type, len(data)
    audit.record(db, user, request, "update", "guarantee_letter", g.id, {"number": g.number, "file": g.file_name, "size": g.file_size})
    db.commit()
    return letter_out(db, g)


@router.get("/insurance/guarantee-letters/{letter_id}/file", tags=[TAG], summary="Kafolat xati skanini yuklab olish (auditga yoziladi)")
def download_letter_file(letter_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    g = _letter(db, letter_id)
    storage = get_storage()
    if not g.file_key:
        raise HTTPException(404, "Fayl biriktirilmagan")
    if not storage.exists(g.file_key):
        raise HTTPException(410, "Fayl saqlashda topilmadi")
    audit.record_read(db, user, request, "guarantee_letter", g.id, {"number": g.number, "filename": g.file_name, "download": True})
    return StreamingResponse(storage.open(g.file_key), media_type=g.file_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(g.file_name)}", "Content-Length": str(g.file_size), "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store"})
