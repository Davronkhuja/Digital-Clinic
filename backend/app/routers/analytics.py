import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.services import analytics

router = APIRouter()

ALL = Query(False, description="Hamma filial birga (faqat `branches:all`); aks holda faol filial")


def scope(user: CurrentUser, all_branches: bool) -> uuid.UUID | None:
    """Hisobot doirasi: faol filial yoki (administrator uchun) hamma filial."""
    if all_branches:
        if "branches:all" not in user.permissions:
            raise HTTPException(403, "Hamma filial hisoboti uchun ruxsat yo'q: branches:all")
        return None
    return user.branch_id


PERIOD = Query("month", pattern="^(week|month|year|all)$", description="week=7 kun, month=30 kun, year=365 kun, all=hammasi")


@router.get("/analytics/dashboard", tags=["📊 Analytics"], summary="Dashboard statistikasi",
            description="Bemorlar, uchrashuvlar, daromad va oldingi davr bilan solishtirish: hammasi bazadan hisoblanadi.")
def get_dashboard_stats(period: str = PERIOD, all_branches: bool = ALL, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(require("analytics:read"))):
    return analytics.dashboard(db, period, branch_id=scope(user, all_branches))


@router.get("/analytics/reports", tags=["📊 Analytics"], summary="Tahliliy hisobotlar",
            description="Tashxislar, shifokorlar yuklamasi, bo'limlar, demografiya: bazadan hisoblanadi.")
def get_analytics(period: str = PERIOD, all_branches: bool = ALL, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("analytics:read"))):
    return analytics.reports(db, period, branch_id=scope(user, all_branches))


@router.get("/analytics/no-show", tags=["📊 Analytics"], summary="Haftalik kelmay qolish ulushi (eslatma kesimida)",
            description="no_show / (completed + no_show), hafta dushanbadan; eslatma yuborilgan va yuborilmagan alohida.")
def get_no_show(weeks: int = Query(8, ge=1, le=26), all_branches: bool = ALL, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("analytics:read"))):
    return analytics.no_show_weekly(db, weeks, branch_id=scope(user, all_branches))
