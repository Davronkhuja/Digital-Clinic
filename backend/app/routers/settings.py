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

# ── SETTINGS ──────────────────────────────────
@router.get("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings,
         summary="Klinika sozlamalari", description="Joriy klinika sozlamalarini olish.")
def get_settings(_=Depends(get_current_user)):
    return fake.clinic_settings

@router.put("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings,
         summary="Sozlamalarni yangilash")
def update_settings(data: ClinicSettings, _=Depends(get_current_user)):
    fake.clinic_settings = data
    return fake.clinic_settings
