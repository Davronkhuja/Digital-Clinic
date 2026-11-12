"""MKB-10 ro'yxatini CSV fayldan import qilish (idempotent).

Ishlatish (konteyner ichida):
    docker compose exec backend python scripts/import_mkb10.py /app/data/mkb10_full.csv [--source "Manba nomi"]
CSV ustunlari: code, name_uz[, name_en].
Importdan keyin yozuvlar `verified=true` bo'ladi va `source` yoziladi (fayl nomida "starter" bo'lsa: false, namuna).
Repodagi starter to'plam rasmiy emas: shifokor tekshirishi shart.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.icd10 import import_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path)
    parser.add_argument("--source", help="Manba (standart: fayl nomi)")
    args = parser.parse_args()
    verified = "starter" not in args.file.stem.lower()
    with SessionLocal() as db:
        stats = import_csv(db, args.file, verified=verified, source=args.source or args.file.name)
        db.commit()
    kind = "tasdiqlangan" if verified else "namuna"
    print(f"MKB-10 ({kind}): yaratildi {stats['created']}, yangilandi {stats['updated']}, o'tkazib yuborildi {stats['skipped']}")


if __name__ == "__main__":
    main()
