# ruff: noqa: E501
import json
import uuid
from decimal import Decimal
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
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
    InsuranceRegistry,
    Insurer,
    InsurerPayment,
    Patient,
    PatientPolicy,
    Service,
)
from app.schemas import (
    ContractIn,
    ContractOut,
    ContractUpdate,
    DebtOut,
    InsurerIn,
    InsurerOut,
    InsurerPaymentIn,
    InsurerPaymentOut,
    InsurerUpdate,
    LetterCancelIn,
    LetterIn,
    LetterOut,
    LetterUpdate,
    PolicyIn,
    PolicyOut,
    PolicyUpdate,
    RegistryCreateIn,
    RegistryDetail,
    RegistryOut,
    RegistryReconcileIn,
    ReverseIn,
)
from app.services import attachments as att
from app.services import audit, commissions
from app.services import insurance as ins
from app.services import insurance_registry as reg_svc
from app.services.lookup import get_patient_or_404
from app.services.periods import clinic_today
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


# ---------- Kompaniya to'lovlari, qarzdorlik, reyestr ----------

def payment_out(db: Session, p: InsurerPayment) -> dict:
    return {"id": str(p.id), "insurer_id": str(p.insurer_id), "insurer": db.get(Insurer, p.insurer_id).name, "amount": p.amount, "paid_on": p.paid_on, "reference": p.reference,
            "notes": p.notes, "registry_id": str(p.registry_id) if p.registry_id else None, "reversed": p.reversed_at is not None, "reverse_reason": p.reverse_reason, "created_at": p.created_at.isoformat()}


@router.post("/insurance/payments", tags=[TAG], response_model=InsurerPaymentOut, status_code=201, summary="Kompaniyadan kelgan to'lovni yozish",
             description="Bank o'tkazmasi: eng eski sug'urta ulushlariga (FIFO) taqsimlanib qarz kamayadi. O'zgarmaydi va o'chirilmaydi: xato bo'lsa `reverse`. `insurance:manage`.")
def create_insurer_payment(data: InsurerPaymentIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    insurer = db.get(Insurer, _uuid(data.insurer_id, "insurer_id"))
    if not insurer:
        raise HTTPException(422, "Kompaniya topilmadi")
    paid_on = data.paid_on or clinic_today()
    if paid_on > clinic_today():
        raise HTTPException(422, "To'lov sanasi kelajakda bo'lishi mumkin emas")
    registry = None
    if data.registry_id:
        registry = db.get(InsuranceRegistry, _uuid(data.registry_id, "registry_id"))
        if not registry or registry.insurer_id != insurer.id:
            raise HTTPException(422, "Reyestr topilmadi yoki boshqa kompaniyaniki")
        if registry.status != "Sent":
            raise HTTPException(409, "To'lovni faqat yuborilgan (Sent) reyestrga bog'lash mumkin")
    p = InsurerPayment(insurer_id=insurer.id, amount=data.amount, paid_on=paid_on, reference=(data.reference or "").strip() or None, notes=data.notes,
                       registry_id=registry.id if registry else None, branch_id=user.branch_id, created_by=user.id)
    db.add(p)
    db.flush()
    entries = commissions.reconcile_insurer(db, insurer.id, p, user.id)
    audit.record(db, user, request, "create", "insurer_payment", p.id, {"insurer": insurer.name, "amount": str(p.amount), "reference": p.reference,
                                                                        "commission_entries": len(entries)})
    db.commit()
    return payment_out(db, p)


@router.get("/insurance/payments", tags=[TAG], response_model=List[InsurerPaymentOut], summary="Kompaniya to'lovlari")
def list_insurer_payments(insurer_id: Optional[uuid.UUID] = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db),
                          user: CurrentUser = Depends(require("insurance:read"))):
    stmt = select(InsurerPayment).order_by(InsurerPayment.paid_on.desc(), InsurerPayment.created_at.desc()).limit(limit)
    if insurer_id:
        stmt = stmt.where(InsurerPayment.insurer_id == insurer_id)
    return [payment_out(db, p) for p in db.scalars(stmt)]


@router.post("/insurance/payments/{payment_id}/reverse", tags=[TAG], response_model=InsurerPaymentOut, summary="To'lovni bekor qilish (xato kiritilgan)",
             description="Sabab majburiy; qarz qayta oshadi. To'lov o'chirilmaydi.")
def reverse_insurer_payment(payment_id: uuid.UUID, data: ReverseIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    p = db.get(InsurerPayment, payment_id)
    if not p:
        raise HTTPException(404, "To'lov topilmadi")
    if p.reversed_at is not None:
        raise HTTPException(409, "To'lov allaqachon bekor qilingan")
    if p.registry_id and db.get(InsuranceRegistry, p.registry_id).status == "Reconciled":
        raise HTTPException(409, "To'lov solishtirilgan (Reconciled) reyestrga bog'langan: bekor qilib bo'lmaydi")
    from datetime import UTC, datetime
    p.reversed_at, p.reverse_reason = datetime.now(UTC), data.reason.strip()
    db.flush()
    entries = commissions.reconcile_insurer(db, p.insurer_id, p, user.id)
    audit.record(db, user, request, "update", "insurer_payment", p.id, {"reversed": True, "reason": p.reverse_reason, "amount": str(p.amount),
                                                                        "commission_entries": len(entries)})
    db.commit()
    return payment_out(db, p)


@router.get("/insurance/debts", tags=[TAG], response_model=List[DebtOut], summary="Kompaniyalar bo'yicha qarzdorlik (muddat kesimida)",
            description="Sug'urta ulushi (hamma filial) minus kompaniya to'lovlari (FIFO). Muddat: hisob-faktura oyi oxiri + kompaniyaning to'lov kunlari; "
                        "kesim: muddati o'tmagan, 1-30, 31-60, 61-90, 90+ kun. Faqat qarzi yoki to'lovi bor kompaniyalar (`include_zero=true`: hammasi).")
def debts(include_zero: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    out = [ins.receivables(db, i.id) for i in db.scalars(select(Insurer).order_by(Insurer.name))]
    return out if include_zero else [d for d in out if d["charged"] > 0 or d["paid"] > 0]


@router.get("/insurance/debts/{insurer_id}", tags=[TAG], response_model=DebtOut, summary="Bitta kompaniya qarzi (ochiq hisob-fakturalar bilan)")
def debt_detail(insurer_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    if not db.get(Insurer, insurer_id):
        raise HTTPException(404, "Kompaniya topilmadi")
    return ins.receivables(db, insurer_id)


@router.get("/insurance/registry", tags=[TAG], summary="Oylik reyestr (kompaniya bo'yicha): JSON yoki Excel", response_class=Response,
            description="Tanlangan oyda chiqarilgan hisob-fakturalarning sug'urta ulushi bor qatorlari: sana, hisob-faktura, bemor, polis, kafolat xati, xizmat, "
                        "summa, sug'urta va bemor ulushi; jami va xizmatlar bo'yicha varaq. `month=YYYY-MM`. Faol filial; `all_branches=true` (`branches:all`): hamma filial. "
                        "Yuklash auditda. `insurance:manage`.")
def registry(request: Request, insurer_id: uuid.UUID, month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
             file_format: str = Query("json", alias="format", pattern="^(json|xlsx)$"), all_branches: bool = False, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require("insurance:manage"))):
    insurer = db.get(Insurer, insurer_id)
    if not insurer:
        raise HTTPException(404, "Kompaniya topilmadi")
    if all_branches and "branches:all" not in user.permissions:
        raise HTTPException(403, "Hamma filial reyestri uchun ruxsat yo'q: branches:all")
    year, mon = int(month[:4]), int(month[5:])
    rows = ins.registry_rows(db, insurer_id, year, mon, None if all_branches else user.branch_id)
    total = sum((r["insurer_amount"] for r in rows), Decimal(0))
    number = f"REE-{month.replace('-', '')}-{str(insurer.id)[:4].upper()}"
    summary: dict[str, list] = {}
    for r in rows:
        a = summary.setdefault(r["service"], [0, Decimal(0), Decimal(0)])
        a[0] += r["qty"]
        a[1] += r["line_total"]
        a[2] += r["insurer_amount"]
    head = {"number": number, "insurer": insurer.name, "tin": insurer.tin, "month": month, "invoices": len({r["invoice"] for r in rows}), "lines": len(rows),
            "insurer_total": total, "patient_total": sum((r["patient_amount"] for r in rows), Decimal(0)), "payment_days": insurer.payment_days}
    if file_format == "json":
        from fastapi.encoders import jsonable_encoder
        return Response(json.dumps(jsonable_encoder({"header": head, "rows": rows}, custom_encoder={Decimal: float}), ensure_ascii=False), media_type="application/json")
    audit.record_read(db, user, request, "insurance_registry", insurer.id, {"month": month, "rows": len(rows), "total": str(total), "all_branches": all_branches})
    from app.services.exports import XLSX
    return Response(ins.registry_xlsx(db, head, rows, summary, user.branch_id if not all_branches else None), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{number}.xlsx"'})


# ---------- Reyestr hujjati: Draft -> Sent (qotgan, Excel saqlanadi) -> Reconciled ----------

def _registry(db: Session, registry_id: uuid.UUID, user: CurrentUser) -> InsuranceRegistry:
    reg = db.get(InsuranceRegistry, registry_id)
    if not reg or (reg.branch_id != user.branch_id and "branches:all" not in user.permissions):
        raise HTTPException(404, "Reyestr topilmadi")
    return reg


def registry_out(db: Session, reg: InsuranceRegistry, rows: list[dict] | None = None, with_rows: bool = False) -> dict:
    rows = rows if rows is not None else reg_svc.rows_of(db, reg)
    head = reg_svc.head_of(db, reg, rows)
    paid = reg_svc.paid_total(db, reg.id)
    out = {"id": str(reg.id), "number": reg.number, "insurer_id": str(reg.insurer_id), "insurer": head["insurer"], "month": head["month"], "status": reg.status,
           "insurer_total": head["insurer_total"], "patient_total": head["patient_total"], "lines_count": head["lines"], "invoices_count": head["invoices"],
           "corrections": head["corrections"], "paid": paid, "balance": head["insurer_total"] - paid, "file_name": reg.file_name, "file_sha256": reg.file_sha256,
           "sent_at": reg.sent_at.isoformat() if reg.sent_at else None, "reconciled_at": reg.reconciled_at.isoformat() if reg.reconciled_at else None,
           "reconcile_note": reg.reconcile_note}
    if with_rows:
        out["rows"] = [{**r, "invoice_line_id": str(r["invoice_line_id"])} for r in rows]
    return out


@router.post("/insurance/registries", tags=[TAG], response_model=RegistryDetail, status_code=201, summary="Reyestr hujjatini ochish (Draft)",
             description="Kompaniya + oy + faol filial uchun bitta hujjat. Draft: qatorlar jonli hisoblanadi (oy oxirigacha chiqarilgan va hali yuborilmagan qatorlar + "
                         "avval yuborilgan qatorlarga tuzatishlar). `insurance:manage`.")
def create_registry(data: RegistryCreateIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    insurer = db.get(Insurer, _uuid(data.insurer_id, "insurer_id"))
    if not insurer:
        raise HTTPException(422, "Kompaniya topilmadi")
    first = reg_svc.month_first(data.month)
    reg = InsuranceRegistry(insurer_id=insurer.id, month=first, number=reg_svc.make_number(insurer.id, first, user.branch_id), status="Draft",
                            branch_id=user.branch_id, created_by=user.id)
    db.add(reg)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu kompaniya va oy uchun reyestr allaqachon ochilgan")
    audit.record(db, user, request, "create", "insurance_registry_doc", reg.id, {"number": reg.number, "insurer": insurer.name, "month": data.month})
    db.commit()
    return registry_out(db, reg, with_rows=True)


@router.get("/insurance/registries", tags=[TAG], response_model=List[RegistryOut], summary="Reyestr hujjatlari")
def list_registries(insurer_id: Optional[uuid.UUID] = None, status: Optional[str] = Query(None, pattern="^(Draft|Sent|Reconciled)$"),
                    db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    stmt = select(InsuranceRegistry).where(InsuranceRegistry.branch_id == user.branch_id).order_by(InsuranceRegistry.month.desc(), InsuranceRegistry.number)
    if insurer_id:
        stmt = stmt.where(InsuranceRegistry.insurer_id == insurer_id)
    if status:
        stmt = stmt.where(InsuranceRegistry.status == status)
    return [registry_out(db, r) for r in db.scalars(stmt)]


@router.get("/insurance/registries/{registry_id}", tags=[TAG], response_model=RegistryDetail, summary="Reyestr hujjati qatorlari bilan",
            description="Draft: jonli hisob; Sent/Reconciled: qotgan nusxa (o'zgarmaydi). `Correction` qatorlari avval yuborilgan qatordan farqni ko'rsatadi.")
def get_registry(registry_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:read"))):
    reg = _registry(db, registry_id, user)
    audit.record_read(db, user, request, "insurance_registry_doc", reg.id, {"number": reg.number, "status": reg.status})
    return registry_out(db, reg, with_rows=True)


@router.post("/insurance/registries/{registry_id}/send", tags=[TAG], response_model=RegistryDetail, summary="Reyestrni yuborish (qotirish)",
             description="Draft -> Sent: qatorlar qotadi, Excel fayli saqlanadi (SHA-256 bilan) va hujjat o'zgarmaydi. Bo'sh reyestr yuborilmaydi (409). "
                         "Keyin o'zgargan hisob-faktura keyingi reyestrga tuzatish qatori bo'lib tushadi. `insurance:manage`.")
def send_registry(registry_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    from datetime import UTC, datetime
    reg = _registry(db, registry_id, user)
    if reg.status != "Draft":
        raise HTTPException(409, "Reyestr allaqachon yuborilgan")
    rows = reg_svc.live_rows(db, reg.insurer_id, reg.month, reg.branch_id)
    if not rows:
        raise HTTPException(409, "Reyestrda qator yo'q: yuborib bo'lmaydi")
    xlsx = reg_svc.xlsx_of(db, reg, rows)
    key = f"{uuid.uuid4().hex}.xlsx"
    get_storage().save(key, xlsx)
    reg_svc.freeze(db, reg, rows, xlsx, key, user.id, datetime.now(UTC))
    audit.record(db, user, request, "update", "insurance_registry_doc", reg.id, {"number": reg.number, "status": "Sent", "lines": reg.lines_count,
                                                                                 "insurer_total": str(reg.insurer_total), "sha256": reg.file_sha256})
    db.commit()
    return registry_out(db, reg, with_rows=True)


@router.get("/insurance/registries/{registry_id}/file", tags=[TAG], summary="Reyestr Excel fayli (yuborilgan: saqlangan nusxa; Draft: hozirgi holat)",
            response_class=Response)
def registry_file(registry_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("insurance:manage"))):
    from app.services.exports import XLSX
    reg = _registry(db, registry_id, user)
    if reg.status == "Draft":
        content = reg_svc.xlsx_of(db, reg, reg_svc.live_rows(db, reg.insurer_id, reg.month, reg.branch_id))
    else:
        storage = get_storage()
        if not storage.exists(reg.file_key):
            raise HTTPException(410, "Fayl saqlashda topilmadi")
        content = b"".join(storage.open(reg.file_key))
    audit.record_read(db, user, request, "insurance_registry_doc", reg.id, {"number": reg.number, "status": reg.status, "download": True})
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{reg.number}.xlsx"', "X-Content-Type-Options": "nosniff"})


@router.post("/insurance/registries/{registry_id}/reconcile", tags=[TAG], response_model=RegistryDetail, summary="Reyestrni solishtirish (Reconciled)",
             description="Sent -> Reconciled: bog'langan kompaniya to'lovlari reyestr summasiga yetgan bo'lsa; kam bo'lsa farq sababi (`note`) majburiy. "
                         "Solishtirilgan reyestr va unga bog'langan to'lovlar o'zgarmaydi. `insurance:manage`.")
def reconcile_registry(registry_id: uuid.UUID, data: RegistryReconcileIn, request: Request, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("insurance:manage"))):
    from datetime import UTC, datetime
    reg = _registry(db, registry_id, user)
    if reg.status != "Sent":
        raise HTTPException(409, "Faqat yuborilgan (Sent) reyestr solishtiriladi")
    paid = reg_svc.paid_total(db, reg.id)
    note = (data.note or "").strip() or None
    if paid < reg.insurer_total and (not note or len(note) < 5):
        raise HTTPException(422, f"To'lov reyestr summasidan kam ({paid} / {reg.insurer_total}): farq sababini `note` da yozing")
    reg.status, reg.reconciled_at, reg.reconciled_by, reg.reconcile_note, reg.paid_at_reconcile = "Reconciled", datetime.now(UTC), user.id, note, paid
    audit.record(db, user, request, "update", "insurance_registry_doc", reg.id, {"number": reg.number, "status": "Reconciled", "paid": str(paid),
                                                                                 "insurer_total": str(reg.insurer_total), "note": note})
    db.commit()
    return registry_out(db, reg, with_rows=True)
