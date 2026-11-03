from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.models import ClinicSettings as ClinicSettingsRow
from app.schemas import ClinicSettings

router = APIRouter()


def _row(db: Session, user: CurrentUser) -> ClinicSettingsRow:
    row = db.scalar(select(ClinicSettingsRow).where(ClinicSettingsRow.branch_id == user.branch_id))
    if not row:
        raise HTTPException(404, "Sozlamalar topilmadi")
    return row


def _out(row: ClinicSettingsRow) -> dict:
    return {"clinic_name": row.clinic_name, "address": row.address or "", "phone": row.phone or "",
            "email": row.email or "", "currency": row.currency, "timezone": row.timezone, "language": row.language}


@router.get("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings, summary="Klinika sozlamalari")
def get_settings(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return _out(_row(db, user))


@router.put("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings, summary="Sozlamalarni yangilash")
def update_settings(data: ClinicSettings, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    row = _row(db, user)
    row.clinic_name, row.address, row.phone, row.email = data.clinic_name, data.address, data.phone, data.email
    row.currency, row.timezone, row.language = data.currency, data.timezone, data.language
    db.commit()
    return _out(row)
