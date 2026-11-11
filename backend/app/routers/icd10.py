from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.schemas.emr import Icd10Out
from app.services import icd10

router = APIRouter()


@router.get("/icd10", tags=["📋 EMR"], response_model=List[Icd10Out], summary="MKB-10 qidiruvi",
            description="Kod boshi (I1), o'zbekcha yoki inglizcha nom bo'yicha.")
def search_icd10(search: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:read"))):
    return icd10.search(db, search, limit)


@router.get("/icd10/{code}", tags=["📋 EMR"], response_model=Icd10Out, summary="MKB-10 kodi")
def get_icd10(code: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:read"))):
    found = [c for c in icd10.search(db, icd10.normalize_code(code), 100) if c.code == icd10.normalize_code(code)]
    if not found:
        raise HTTPException(404, "MKB-10 kodi topilmadi")
    return found[0]
