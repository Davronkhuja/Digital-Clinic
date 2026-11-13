from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import ClinicSettings as ClinicSettingsRow
from app.schemas import ClinicSettings
from app.schemas.common import Money
from app.services import audit

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
def get_settings(db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:read"))):
    return _out(_row(db, user))


@router.put("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings, summary="Sozlamalarni yangilash")
def update_settings(data: ClinicSettings, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("settings:write"))):
    row = _row(db, user)
    row.clinic_name, row.address, row.phone, row.email = data.clinic_name, data.address, data.phone, data.email
    row.currency, row.timezone, row.language = data.currency, data.timezone, data.language
    db.commit()
    return _out(row)


class FinanceSettings(BaseModel):
    commission_base: Literal["NetOfVat", "WithVat"] = Field(
        "NetOfVat", description="Foiz asosi: chegirmadan keyin QQS'siz (standart) yoki QQS bilan")
    discount_limit_percent: Money = Field(..., ge=0, le=100, max_digits=5, decimal_places=2,
                                            description="Kassir (finance:discount) bera oladigan eng katta chegirma, %")


@router.get("/settings/finance", tags=["⚙️ Settings"], response_model=FinanceSettings, summary="Moliya sozlamalari")
def get_finance_settings(db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:read"))):
    row = _row(db, user)
    return {"discount_limit_percent": row.discount_limit_percent, "commission_base": row.commission_base}


@router.put("/settings/finance", tags=["⚙️ Settings"], response_model=FinanceSettings, summary="Moliya sozlamalarini yangilash",
            description="Chegirma limiti keyingi hisob-fakturalarga ta'sir qiladi (yozilganlari o'zgarmaydi). Auditga yoziladi.")
def update_finance_settings(data: FinanceSettings, request: Request, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(require("settings:write"))):
    row = _row(db, user)
    old = row.discount_limit_percent, row.commission_base
    row.discount_limit_percent, row.commission_base = data.discount_limit_percent, data.commission_base
    audit.record(db, user, request, "update", "settings", row.id, {
        "discount_limit_percent": {"from": str(old[0]), "to": str(data.discount_limit_percent)},
        "commission_base": {"from": old[1], "to": data.commission_base}})
    db.commit()
    return {"discount_limit_percent": row.discount_limit_percent, "commission_base": row.commission_base}


class MessagingSettings(BaseModel):
    quiet_start_hour: int = Field(21, ge=0, le=23, description="Tungi vaqt boshlanishi (klinika vaqti, soat)")
    quiet_end_hour: int = Field(8, ge=0, le=23, description="Tungi vaqt tugashi (shu soatdan yuboriladi)")


@router.get("/settings/messaging", tags=["⚙️ Settings"], response_model=MessagingSettings, summary="Xabar sozlamalari (tungi vaqt)")
def get_messaging_settings(db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:read"))):
    row = _row(db, user)
    return {"quiet_start_hour": row.quiet_start_hour, "quiet_end_hour": row.quiet_end_hour}


@router.put("/settings/messaging", tags=["⚙️ Settings"], response_model=MessagingSettings, summary="Tungi vaqtni o'zgartirish",
            description="Tungi vaqtda eslatmalar yuborilmaydi, ertalabga qoldiriladi (OTP mustasno). Boshlanish va tugash farq qilsin.")
def update_messaging_settings(data: MessagingSettings, request: Request, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(require("settings:write"))):
    if data.quiet_start_hour == data.quiet_end_hour:
        raise HTTPException(422, "Tungi vaqt boshlanishi va tugashi bir xil bo'lmasligi kerak")
    row = _row(db, user)
    old = {"quiet_start_hour": row.quiet_start_hour, "quiet_end_hour": row.quiet_end_hour}
    row.quiet_start_hour, row.quiet_end_hour = data.quiet_start_hour, data.quiet_end_hour
    audit.record(db, user, request, "update", "settings", row.id, {"messaging": {"from": old, "to": data.model_dump()}})
    db.commit()
    return data.model_dump()
