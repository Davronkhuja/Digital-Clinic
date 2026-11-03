import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.services import audit, queries

router = APIRouter()

REPORTS = [
    {"id": "1", "name": "Oylik moliyaviy hisobot", "type": "finance"},
    {"id": "2", "name": "Bemorlar statistikasi", "type": "patients"},
    {"id": "3", "name": "Xodimlar faoliyati", "type": "staff"},
    {"id": "4", "name": "Uchrashuvlar tahlili", "type": "appointments"},
]

SOURCES = {
    "1": ("moliyaviy_hisobot", lambda db: queries.list_transactions(db)),
    "2": ("bemorlar_statistikasi", lambda db: queries.list_patients(db, limit=100000)),
    "3": ("xodimlar_faoliyati", lambda db: queries.list_staff(db)),
    "4": ("uchrashuvlar_tahlili", lambda db: queries.list_appointments(db)),
}


def _csv_cell(value):
    # CSV/formula injection'dan himoya: =, +, -, @ bilan boshlanuvchi matnlar
    text = "" if value is None else (value.value if hasattr(value, "value") else str(value))
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get("/reports", tags=["📝 Reports"], summary="Hisobotlar ro'yxati")
def get_reports(user: CurrentUser = Depends(require("reports:read"))):
    return {"reports": REPORTS}


@router.post("/reports/generate/{report_id}", tags=["📝 Reports"], summary="Hisobot generatsiya qilish")
def generate_report(report_id: str, user: CurrentUser = Depends(require("reports:read"))):
    if report_id not in SOURCES:
        raise HTTPException(404, "Hisobot topilmadi")
    return {"status": "generated", "report_id": report_id, "download_url": f"/reports/download/{report_id}",
            "generated_at": datetime.now().isoformat(), "format": "CSV"}


@router.get("/reports/download/{report_id}", tags=["📝 Reports"],
            summary="Hisobotni CSV sifatida yuklab olish",
            description="UTF-8 BOM bilan CSV (Excel to'g'ri ochadi). Authorization header talab qilinadi.")
def download_report(report_id: str, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("reports:read"))):
    if report_id not in SOURCES:
        raise HTTPException(404, "Hisobot topilmadi")
    name, source = SOURCES[report_id]
    rows = source(db)
    audit.record_read(db, user, request, "report", details={"report_id": report_id, "rows": len(rows)})
    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow([_csv_cell(v) for v in r.values()])
    return Response(
        content=("\ufeff" + buf.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}_{date.today().isoformat()}.csv"'},
    )
