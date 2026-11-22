from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Lock

from app.config import settings
from app.schemas import Book


class LibraryRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def list(self) -> list[Book]:
        with self._lock:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        return [Book.model_validate(row) for row in rows]

    def get(self, book_id: str) -> Book | None:
        return next((book for book in self.list() if book.id == book_id), None)

    def add(self, *, book_id: str, title: str, filename: str, chunks: int) -> Book:
        suffix = Path(filename).suffix.lower().lstrip(".")
        book = Book(
            id=book_id,
            title=title,
            filename=filename,
            file_type=suffix,
            chunks=chunks,
            added_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            rows = [row for row in rows if row["id"] != book_id]
            rows.append(book.model_dump())
            self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        return book

    def remove(self, book_id: str) -> bool:
        with self._lock:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            filtered = [row for row in rows if row["id"] != book_id]
            changed = len(rows) != len(filtered)
            if changed:
                self.path.write_text(
                    json.dumps(filtered, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        return changed


def content_id(content: bytes) -> str:
    return sha256(content).hexdigest()[:20]


registry = LibraryRegistry(settings.data_dir / "library.json")
