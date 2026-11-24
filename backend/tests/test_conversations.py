from pathlib import Path

from app.conversations import ConversationStore
from app.schemas import Source


def test_conversation_lifecycle(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations.db")
    created = store.create("book-1", "  Why does Mira leave?  ")

    assert created.title == "Why does Mira leave?"
    assert created.message_count == 0

    store.add_exchange(
        created.id,
        "Why does Mira leave?",
        "Mira leaves to find the archive. [1]",
        [
            Source(
                index=1,
                book_id="book-1",
                title="Tiny Novel",
                excerpt="Mira packed the map and left before dawn.",
            )
        ],
    )

    detail = store.get(created.id)
    assert detail is not None
    assert detail.message_count == 2
    assert [message.role for message in detail.messages] == ["user", "assistant"]
    assert detail.messages[1].sources[0].title == "Tiny Novel"
    assert store.list()[0].id == created.id

    assert store.delete(created.id)
    assert store.get(created.id) is None


def test_suggestions_are_cached_per_book(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "suggestions.db")
    assert store.get_suggestions("book-1") is None

    suggestions = ["What motivates Mira?", "How does the archive work?", "Why is the map important?"]
    store.save_suggestions("book-1", suggestions)

    assert store.get_suggestions("book-1") == suggestions
    store.delete_suggestions("book-1")
    assert store.get_suggestions("book-1") is None


def test_conversations_can_be_deleted_with_their_book(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "book-cleanup.db")
    first = store.create("book-1", "First question")
    store.create("book-2", "Another question")

    assert store.delete_for_book("book-1") == 1
    assert store.get(first.id) is None
    assert len(store.list()) == 1
