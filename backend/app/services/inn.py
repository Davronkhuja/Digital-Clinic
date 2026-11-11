"""INN ma'lumotnomasi: CSV import (idempotent), qidiruv, kanonik nom."""
import csv
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import InnDrug

STARTER_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "inn_starter.csv"


def import_csv(db: Session, path: Path) -> dict[str, int]:
    """CSV ustunlari: inn[, group_uz]. Registrsiz moslik bo'yicha yangilanadi."""
    existing = {d.inn.lower(): d for d in db.scalars(select(InnDrug))}
    stats = {"created": 0, "updated": 0, "skipped": 0}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = " ".join((row.get("inn") or "").split())
            if len(name) < 2:
                stats["skipped"] += 1
                continue
            group = (row.get("group_uz") or "").strip() or None
            if name.lower() in existing:
                rec = existing[name.lower()]
                rec.group_uz, rec.is_active = group, True
                stats["updated"] += 1
            else:
                rec = InnDrug(inn=name, group_uz=group)
                db.add(rec)
                existing[name.lower()] = rec
                stats["created"] += 1
    db.flush()
    return stats


def seed_starter(db: Session) -> None:
    if not db.scalar(select(func.count()).select_from(InnDrug)) and STARTER_CSV.exists():
        import_csv(db, STARTER_CSV)


def search(db: Session, query: str | None, limit: int = 20) -> list[InnDrug]:
    stmt = select(InnDrug).where(InnDrug.is_active.is_(True)).order_by(InnDrug.inn).limit(limit)
    if query and query.strip():
        q = query.strip()
        stmt = stmt.where(InnDrug.inn.ilike(f"{q}%") | InnDrug.inn.ilike(f"% {q}%") | InnDrug.group_uz.ilike(f"%{q}%"))
    return list(db.scalars(stmt))


def canonical(db: Session, name: str) -> InnDrug | None:
    return db.scalar(select(InnDrug).where(func.lower(InnDrug.inn) == " ".join(name.split()).lower(),
                                           InnDrug.is_active.is_(True)))
