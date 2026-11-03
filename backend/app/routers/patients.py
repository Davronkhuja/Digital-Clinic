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

# ── PATIENTS ──────────────────────────────────
@router.get("/patients", tags=["👥 Patients"], response_model=List[Patient],
         summary="Barcha bemorlar ro'yxati",
         description="Barcha bemorlarni oling. Qidiruv va filtrlash imkoniyati mavjud.")
def get_patients(
    search: Optional[str] = Query(None, description="Ism bo'yicha qidiruv"),
    status: Optional[StatusEnum] = Query(None, description="Status bo'yicha filter"),
    skip: int = Query(0, ge=0, description="Nechta yozuvni o'tkazib yuborish"),
    limit: int = Query(10, ge=1, le=100, description="Nechta yozuv qaytarish"),
    _=Depends(get_current_user)
):
    results = fake.fake_patients
    if search:
        results = [p for p in results if search.lower() in p.name.lower()]
    if status:
        results = [p for p in results if p.status == status]
    return results[skip:skip + limit]

@router.post("/patients", tags=["👥 Patients"], response_model=Patient,
          status_code=status.HTTP_201_CREATED,
          summary="Yangi bemor qo'shish", description="Yangi bemor ma'lumotlarini tizimga kiritish.")
def create_patient(data: PatientCreate, _=Depends(get_current_user)):
    patient = Patient(**data.model_dump(), id=new_id(),
                      created_at=datetime.now().isoformat()[:10])
    fake.fake_patients.append(patient)
    return patient

@router.get("/patients/{patient_id}", tags=["👥 Patients"], response_model=Patient,
         summary="Bemor ma'lumotlari", description="Bemor ID si orqali to'liq ma'lumot olish.")
def get_patient(patient_id: str, _=Depends(get_current_user)):
    patient = next((p for p in fake.fake_patients if p.id == patient_id), None)
    if not patient:
        raise HTTPException(status_code=404, detail="Bemor topilmadi")
    return patient

@router.put("/patients/{patient_id}", tags=["👥 Patients"], response_model=Patient,
         summary="Bemor ma'lumotlarini yangilash")
def update_patient(patient_id: str, data: PatientUpdate, _=Depends(get_current_user)):
    for i, p in enumerate(fake.fake_patients):
        if p.id == patient_id:
            updated = p.model_dump()
            updated.update({k: v for k, v in data.model_dump().items() if v is not None})
            fake.fake_patients[i] = Patient(**updated)
            return fake.fake_patients[i]
    raise HTTPException(status_code=404, detail="Bemor topilmadi")

@router.delete("/patients/{patient_id}", tags=["👥 Patients"],
            summary="Bemor o'chirish", description="Bemor yozuvini tizimdan o'chirish.")
def delete_patient(patient_id: str, _=Depends(get_current_user)):
    patient = next((p for p in fake.fake_patients if p.id == patient_id), None)
    if not patient:
        raise HTTPException(status_code=404, detail="Bemor topilmadi")
    fake.fake_patients = [p for p in fake.fake_patients if p.id != patient_id]
    return {"message": "Bemor muvaffaqiyatli o'chirildi"}
