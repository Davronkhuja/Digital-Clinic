"""Fayl saqlash interfeysi. Hozir lokal papka (docker volume); S3/MinIO uchun `Storage` ni amalga oshiring va
`get_storage()` da `STORAGE_BACKEND` bo'yicha tanlang. Kalit (key) faqat server yaratadi (foydalanuvchi nomi yo'lga kirmaydi)."""
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from app.core.config import settings

CHUNK = 64 * 1024


class Storage(Protocol):
    def save(self, key: str, data: bytes) -> None: ...

    def open(self, key: str) -> Iterator[bytes]: ...

    def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key[:2] / key).resolve()
        if self.root not in path.parents:  # kalit papkadan chiqib ketmasin
            raise ValueError("Noto'g'ri saqlash kaliti")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent)  # atomik: yarim yozilgan fayl ko'rinmaydi
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def open(self, key: str) -> Iterator[bytes]:
        with open(self._path(key), "rb") as fh:
            while chunk := fh.read(CHUNK):
                yield chunk

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def get_storage() -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_dir)
    raise RuntimeError(f"Noma'lum STORAGE_BACKEND: {settings.storage_backend}")
