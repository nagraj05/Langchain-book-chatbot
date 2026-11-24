from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.schemas import ConversationDetail, ConversationSummary, Source, StoredMessage


class ConversationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS messages_conversation_id
                ON messages(conversation_id, id);
                CREATE TABLE IF NOT EXISTS book_suggestions (
                    book_id TEXT PRIMARY KEY,
                    suggestions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create(self, book_id: str, title: str) -> ConversationSummary:
        conversation_id = uuid4().hex
        now = _now()
        clean_title = " ".join(title.split())[:80] or "New conversation"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (id, title, book_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, clean_title, book_id, now, now),
            )
        conversation = self.get_summary(conversation_id)
        if conversation is None:  # pragma: no cover - protects against storage corruption.
            raise RuntimeError("Conversation was not created.")
        return conversation

    def list(self) -> list[ConversationSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [_summary(row) for row in rows]

    def get_summary(self, conversation_id: str) -> ConversationSummary | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (conversation_id,),
            ).fetchone()
        return _summary(row) if row else None

    def get(self, conversation_id: str) -> ConversationDetail | None:
        summary = self.get_summary(conversation_id)
        if summary is None:
            return None
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, sources_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id
                """,
                (conversation_id,),
            ).fetchall()
        messages = [
            StoredMessage(
                role=row["role"],
                content=row["content"],
                sources=[Source.model_validate(source) for source in json.loads(row["sources_json"])],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return ConversationDetail(**summary.model_dump(), messages=messages)

    def add_exchange(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        sources: list[Source],
    ) -> None:
        now = _now()
        serialized_sources = json.dumps(
            [source.model_dump(mode="json") for source in sources], ensure_ascii=False
        )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO messages (conversation_id, role, content, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (conversation_id, "user", question, "[]", now),
                    (conversation_id, "assistant", answer, serialized_sources, now),
                ],
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def delete(self, conversation_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
        return cursor.rowcount > 0

    def delete_for_book(self, book_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM conversations WHERE book_id = ?", (book_id,))
        return cursor.rowcount

    def get_suggestions(self, book_id: str) -> list[str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT suggestions_json FROM book_suggestions WHERE book_id = ?",
                (book_id,),
            ).fetchone()
        return json.loads(row["suggestions_json"]) if row else None

    def save_suggestions(self, book_id: str, suggestions: list[str]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO book_suggestions (book_id, suggestions_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    suggestions_json = excluded.suggestions_json,
                    created_at = excluded.created_at
                """,
                (book_id, json.dumps(suggestions, ensure_ascii=False), _now()),
            )

    def delete_suggestions(self, book_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM book_suggestions WHERE book_id = ?", (book_id,))


def _summary(row: sqlite3.Row) -> ConversationSummary:
    return ConversationSummary(
        id=row["id"],
        title=row["title"],
        book_id=row["book_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        message_count=row["message_count"],
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


conversation_store = ConversationStore(settings.data_dir / "bookbot.db")
