import csv  # noqa: F401
import io  # noqa: F401
from datetime import date, datetime  # noqa: F401
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from fastapi.responses import Response  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import *  # noqa: F401,F403
from app.db import fake  # noqa: F401
from app.schemas import *  # noqa: F401,F403

router = APIRouter()

# ── EMR ───────────────────────────────────────
@router.get("/emr", tags=["📋 EMR"], response_model=List[EMRRecord],
         summary="Tibbiy yozuvlar ro'yxati",
         description="Barcha elektron tibbiy yozuvlarni (EMR) olish.")
def get_emr(patient_id: Optional[str] = Query(None), _=Depends(get_current_user)):
    if patient_id:
        return [r for r in fake.fake_emr if r.patient_id == patient_id]
    return fake.fake_emr

@router.post("/emr", tags=["📋 EMR"], response_model=EMRRecord, status_code=201,
          summary="Yangi tibbiy yozuv qo'shish")
def create_emr(data: EMRCreate, _=Depends(get_current_user)):
    record = EMRRecord(**data.model_dump(), id=new_id(),
                       created_at=datetime.now().isoformat()[:10])
    fake.fake_emr.append(record)
    return record

@router.get("/emr/{record_id}", tags=["📋 EMR"], response_model=EMRRecord,
         summary="Bitta tibbiy yozuv")
def get_emr_record(record_id: str, _=Depends(get_current_user)):
    record = next((r for r in fake.fake_emr if r.id == record_id), None)
    if not record:
        raise HTTPException(404, "Yozuv topilmadi")
    return record
