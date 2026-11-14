# ruff: noqa: E501
import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.services import audit, queries, report_builder

router = APIRouter()

REPORTS = [
    {"id": "1", "name": "Oylik moliyaviy hisobot", "type": "finance"},
    {"id": "2", "name": "Bemorlar statistikasi", "type": "patients"},
    {"id": "3", "name": "Xodimlar faoliyati", "type": "staff"},
    {"id": "4", "name": "Uchrashuvlar tahlili", "type": "appointments"},
]

SOURCES = {
    "1": ("moliyaviy_hisobot", lambda db, br: queries.list_transactions(db, branch_id=br)),
    "2": ("bemorlar_statistikasi", lambda db, br: queries.list_patients(db, limit=100000)),   # bemor bazasi umumiy
    "3": ("xodimlar_faoliyati", lambda db, br: queries.list_staff(db, branch_id=br)),
    "4": ("uchrashuvlar_tahlili", lambda db, br: queries.list_appointments(db, branch_id=br)),
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
    rows = source(db, user.branch_id)                      # faol filial bo'yicha (bemorlar bazasi umumiy)
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


# ---------- Tahliliy hisobotlar (v1.9.23) ----------

@router.get("/reports/analytics", tags=["📝 Reports"], summary="Tahliliy hisobot turlari")
def analytics_report_kinds(user: CurrentUser = Depends(require("reports:read"))):
    return [{"kind": k, "title": t} for k, t in report_builder.KINDS.items()]


@router.get("/reports/analytics/{kind}", tags=["📝 Reports"], summary="Tahliliy hisobot (JSON, Excel yoki PDF)", response_class=Response,
            description="`kind`: revenue (daromad), patient_flow (bemorlar oqimi), doctor_load (shifokor yuklamasi), no_show (kelmay qolish). `format`: json (standart), "
                        "xlsx, pdf. Davr (standart oxirgi 30 kun, eng ko'pi 400 kun) va filial bo'yicha; `all_branches=true` faqat `branches:all`. `reports:read`; "
                        "yuklash auditda.")
def analytics_report(kind: str, request: Request, file_format: str = Query("json", alias="format", pattern="^(json|xlsx|pdf)$"),
                     date_from: Optional[date] = None, date_to: Optional[date] = None, all_branches: bool = False, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require("reports:read"))):
    if all_branches and "branches:all" not in user.permissions:
        raise HTTPException(403, "Hamma filial hisoboti uchun ruxsat yo'q: branches:all")
    report = report_builder.build(db, kind, None if all_branches else user.branch_id, date_from, date_to)
    if file_format != "json":
        audit.record_read(db, user, request, "report", None, {"analytics": kind, "format": file_format, "from": report["from"], "to": report["to"],
                                                             "all_branches": all_branches})
    if file_format == "xlsx":
        return Response(report_builder.to_xlsx(report), media_type=report_builder.XLSX,
                        headers={"Content-Disposition": f'attachment; filename="{kind}_{report["from"]}_{report["to"]}.xlsx"'})
    if file_format == "pdf":
        return Response(report_builder.to_pdf(report), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{kind}_{report["from"]}_{report["to"]}.pdf"'})
    from fastapi.encoders import jsonable_encoder
    return Response(json.dumps(jsonable_encoder(report, custom_encoder={Decimal: float}), ensure_ascii=False), media_type="application/json")
