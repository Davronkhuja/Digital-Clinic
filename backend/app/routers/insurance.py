# ruff: noqa: E501
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import InsuranceContract, InsuranceContractService, Insurer, Service
from app.schemas import ContractIn, ContractOut, ContractUpdate, InsurerIn, InsurerOut, InsurerUpdate
from app.services import audit

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
