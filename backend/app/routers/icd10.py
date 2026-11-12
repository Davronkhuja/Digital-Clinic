from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Icd10Code
from app.schemas.emr import Icd10Out, VerifyIn, VerifyOut
from app.services import audit, icd10

router = APIRouter()


@router.get("/icd10", tags=["📋 EMR"], response_model=List[Icd10Out], summary="MKB-10 qidiruvi",
            description="Kod boshi (I1), o'zbekcha yoki inglizcha nom bo'yicha.")
def search_icd10(search: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:read"))):
    return [{"code": c.code, "name_uz": c.name_uz, "name_en": c.name_en, "verified": c.verified, "source": c.source}
            for c in icd10.search(db, search, limit)]


@router.get("/icd10/{code}", tags=["📋 EMR"], response_model=Icd10Out, summary="MKB-10 kodi")
def get_icd10(code: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:read"))):
    found = [c for c in icd10.search(db, icd10.normalize_code(code), 100) if c.code == icd10.normalize_code(code)]
    if not found:
        raise HTTPException(404, "MKB-10 kodi topilmadi")
    c = found[0]
    return {"code": c.code, "name_uz": c.name_uz, "name_en": c.name_en, "verified": c.verified, "source": c.source}


@router.post("/icd10/verify", tags=["📋 EMR"], response_model=VerifyOut, summary="MKB-10 yozuvlarini tasdiqlash",
             description="`items` (kodlar) yoki `all=true` (hamma tasdiqlanmaganlar): `verified=true`, `source` yoziladi. Audit.")
def verify_icd10(data: VerifyIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    stmt = select(Icd10Code).where(Icd10Code.verified.is_(False))
    if not data.all:
        if not data.items:
            raise HTTPException(422, "items yoki all=true kerak")
        stmt = stmt.where(Icd10Code.code.in_([icd10.normalize_code(c) for c in data.items]))
    rows = db.scalars(stmt).all()
    for r in rows:
        r.verified, r.source = True, data.source
    audit.record(db, user, request, "update", "icd10", details={"verified": len(rows), "source": data.source, "all": data.all})
    db.commit()
    return {"verified": len(rows)}
