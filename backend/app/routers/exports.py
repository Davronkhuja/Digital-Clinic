# ruff: noqa: E501
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import ExportColumn, ExportFormat
from app.services import audit, exports

router = APIRouter()
TAG = "📤 Exports (buxgalteriya / 1C)"


class ColumnOut(BaseModel):
    key: str
    default_header: str
    kind: str
    header: str
    enabled: bool


class DatasetOut(BaseModel):
    name: str
    title: str
    columns: List[ColumnOut]
    customized: bool


class ColumnIn(BaseModel):
    key: str = Field(..., max_length=40)
    header: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True


class ColumnsIn(BaseModel):
    columns: List[ColumnIn] = Field(..., min_length=1, description="Ustunlar tartib bilan; ro'yxatda yo'q ustunlar o'chiq holda oxirida")


class FormatIO(BaseModel):
    date_format: str = Field("iso", pattern="^(iso|dmy)$", description="iso: 2026-11-30; dmy: 30.11.2026")
    decimal_separator: str = Field(".", pattern=r"^[.,]$")
    csv_delimiter: str = Field(";", pattern="^(;|,|tab)$")


def _dataset(name: str) -> exports.Dataset:
    ds = exports.DATASETS.get(name)
    if not ds:
        raise HTTPException(404, "Ma'lumot to'plami topilmadi")
    return ds


def _dataset_out(db: Session, ds: exports.Dataset) -> dict:
    custom = bool(db.scalar(select(ExportColumn.id).where(ExportColumn.dataset == ds.name).limit(1)))
    return {"name": ds.name, "title": ds.title, "customized": custom,
            "columns": [{"key": c.key, "default_header": c.header, "kind": c.kind, "header": h, "enabled": on} for c, h, on in exports.effective_columns(db, ds)]}


@router.get("/settings/exports", tags=[TAG], response_model=List[DatasetOut], summary="Eksport ustun xaritasi (hamma ma'lumot to'plamlari)")
def get_export_settings(db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:read"))):
    return [_dataset_out(db, ds) for ds in exports.DATASETS.values()]


@router.put("/settings/exports/{dataset}", tags=[TAG], response_model=DatasetOut, summary="Ustun xaritasini tahrirlash",
            description="Ustun sarlavhasi, tartibi va yoqilgan/o'chiriligi (1C ga moslash uchun). Yoqilgan sarlavhalar takrorlanmasin, kamida bitta ustun yoqilgan bo'lsin. `settings:write`, audit.")
def put_export_columns(dataset: str, data: ColumnsIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    ds = _dataset(dataset)
    exports.save_columns(db, ds, [c.model_dump() for c in data.columns], user.id)
    audit.record(db, user, request, "update", "export_columns", None, {"dataset": dataset, "columns": [c.key for c in data.columns if c.enabled]})
    db.commit()
    return _dataset_out(db, ds)


@router.delete("/settings/exports/{dataset}", tags=[TAG], response_model=DatasetOut, summary="Standart ustunlarga qaytarish")
def reset_export_columns(dataset: str, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    ds = _dataset(dataset)
    for r in db.scalars(select(ExportColumn).where(ExportColumn.dataset == ds.name)):
        db.delete(r)
    audit.record(db, user, request, "update", "export_columns", None, {"dataset": dataset, "reset": True})
    db.commit()
    return _dataset_out(db, ds)


@router.get("/settings/export-format", tags=[TAG], response_model=FormatIO, summary="Eksport formati (sana, o'nlik va CSV ajratgichi)")
def get_export_format(db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:read"))):
    f = exports.get_format(db)
    return {"date_format": f.date_format, "decimal_separator": f.decimal_separator, "csv_delimiter": f.csv_delimiter}


@router.put("/settings/export-format", tags=[TAG], response_model=FormatIO, summary="Eksport formatini o'zgartirish",
            description="CSV o'nlik ajratgichi va ustun ajratgichi bir xil bo'lmasin (masalan ikkalasi ','): 422.")
def put_export_format(data: FormatIO, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    if data.decimal_separator == data.csv_delimiter:
        raise HTTPException(422, "O'nlik ajratgich va CSV ustun ajratgichi bir xil bo'lmasin")
    row = db.scalar(select(ExportFormat).limit(1))
    if not row:
        row = ExportFormat(created_by=user.id)
        db.add(row)
    row.date_format, row.decimal_separator, row.csv_delimiter = data.date_format, data.decimal_separator, data.csv_delimiter
    audit.record(db, user, request, "update", "export_format", None, data.model_dump())
    db.commit()
    return data


@router.get("/exports/{dataset}", tags=[TAG], summary="Ma'lumot to'plamini yuklab olish (Excel yoki CSV)", response_class=Response,
            description="`dataset`: sales, payments, cash_shifts, stock_movements, commissions. Davr (standart: oxirgi 30 kun) va filial bo'yicha; faol filial, "
                        "`all_branches=true` (`branches:all`) hamma filial. Ustun nomlari va tartibi Sozlamalar > Eksport bo'yicha. `exports:read`; har yuklash auditda.")
def download(dataset: str, request: Request, file_format: str = Query("xlsx", alias="format", pattern="^(xlsx|csv)$"), date_from: Optional[date] = None,
             date_to: Optional[date] = None, all_branches: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("exports:read"))):
    ds = _dataset(dataset)
    if all_branches and "branches:all" not in user.permissions:
        raise HTTPException(403, "Hamma filial eksporti uchun ruxsat yo'q: branches:all")
    start, end = exports.period(date_from, date_to)
    branch: Optional[uuid.UUID] = None if all_branches else user.branch_id
    rows = ds.query(db, branch, start, end)
    if len(rows) > exports.MAX_ROWS:
        raise HTTPException(422, f"Qatorlar soni {exports.MAX_ROWS} dan oshdi: davrni qisqartiring")
    content, media = exports.render(db, ds, rows, file_format)
    audit.record_read(db, user, request, "export", None, {"dataset": dataset, "rows": len(rows), "format": file_format, "from": str(start), "to": str(end),
                                                         "all_branches": all_branches})
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{dataset}_{start}_{end}.{file_format}"'})
