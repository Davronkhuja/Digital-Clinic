"""MKB-10 ni CSV fayldan import qilish (idempotent).

Ishlatish (konteyner ichida):
    docker compose exec backend python scripts/import_mkb10.py /app/data/mkb10_full.csv
CSV ustunlari: code, name_uz[, name_en]. Fayl rasmiy manbadan bo'lishi kerak; repodagi `data/mkb10_starter.csv`
faqat starter to'plam (shifokor tekshirishi shart).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.icd10 import import_csv  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with SessionLocal() as db:
        stats = import_csv(db, Path(sys.argv[1]))
        db.commit()
    print(f"MKB-10: yaratildi {stats['created']}, yangilandi {stats['updated']}, o'tkazib yuborildi {stats['skipped']}")


if __name__ == "__main__":
    main()
