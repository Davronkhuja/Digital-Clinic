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

# ── REPORTS ───────────────────────────────────
@router.get("/reports", tags=["📝 Reports"],
         summary="Hisobotlar ro'yxati",
         description="Mavjud hisobot shablonlarini ko'rish.")
def get_reports(_=Depends(get_current_user)):
    return {
        "reports": [
            {"id": "1", "name": "Oylik moliyaviy hisobot", "type": "finance", "last_generated": "2026-02-01"},
            {"id": "2", "name": "Bemorlar statistikasi", "type": "patients", "last_generated": "2026-02-15"},
            {"id": "3", "name": "Xodimlar faoliyati", "type": "staff", "last_generated": "2026-02-20"},
            {"id": "4", "name": "Uchrashuvlar tahlili", "type": "appointments", "last_generated": "2026-02-22"},
        ]
    }

@router.post("/reports/generate/{report_id}", tags=["📝 Reports"],
          summary="Hisobot generatsiya qilish",
          description="Berilgan ID bo'yicha hisobot yaratish va yuklash havolasini olish.")
def generate_report(report_id: str, _=Depends(get_current_user)):
    return {
        "status": "generated",
        "report_id": report_id,
        "download_url": f"/reports/download/{report_id}",
        "generated_at": datetime.now().isoformat(),
        "format": "CSV"
    }

REPORT_SOURCES = {
    "1": ("moliyaviy_hisobot", lambda: fake.fake_transactions),
    "2": ("bemorlar_statistikasi", lambda: fake.fake_patients),
    "3": ("xodimlar_faoliyati", lambda: fake.fake_staff),
    "4": ("uchrashuvlar_tahlili", lambda: fake.fake_appointments),
}

def _csv_cell(value):
    # CSV/formula injection'dan himoya: =, +, -, @ bilan boshlanuvchi matnlar
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text

@router.get("/reports/download/{report_id}", tags=["📝 Reports"],
         summary="Hisobotni CSV sifatida yuklab olish",
         description="UTF-8 BOM bilan CSV (Excel to'g'ri ochadi). Authorization header talab qilinadi.")
def download_report(report_id: str, _=Depends(get_current_user)):
    if report_id not in REPORT_SOURCES:
        raise HTTPException(status_code=404, detail="Hisobot topilmadi")
    name, source = REPORT_SOURCES[report_id]
    rows = [r.model_dump(mode="json") for r in source()]
    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow([_csv_cell(v) for v in r.values()])
    content = "\ufeff" + buf.getvalue()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}_{date.today().isoformat()}.csv"'},
    )
