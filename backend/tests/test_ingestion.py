from pathlib import Path

from app.ingestion import extract_documents, split_documents

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_novel.txt"


def test_text_book_is_extracted_and_split() -> None:
    title, documents = extract_documents(FIXTURE.read_bytes(), FIXTURE.name)
    chunks = split_documents(documents)

    assert title == "tiny_novel"
    assert chunks
    assert "Mira Vale" in chunks[0].page_content
    assert chunks[0].metadata["section"] == "tiny_novel"


def test_empty_text_file_is_rejected() -> None:
    try:
        extract_documents(b"   ", "empty.txt")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected an empty file to be rejected")

