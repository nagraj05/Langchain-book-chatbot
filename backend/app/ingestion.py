from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pymupdf as fitz
from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

SUPPORTED_SUFFIXES = {".pdf", ".epub", ".txt", ".md"}


def extract_documents(content: bytes, filename: str) -> tuple[str, list[Document]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Supported formats are PDF, EPUB, TXT, and Markdown.")

    if suffix == ".pdf":
        return _extract_pdf(content, filename)
    if suffix == ".epub":
        return _extract_epub(content, filename)
    return _extract_text(content, filename)


def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=400,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    return [chunk for chunk in chunks if chunk.page_content.strip()]


def _extract_pdf(content: bytes, filename: str) -> tuple[str, list[Document]]:
    pdf = fitz.open(stream=content, filetype="pdf")
    title = (pdf.metadata or {}).get("title") or Path(filename).stem
    documents: list[Document] = []
    for page_number, page in enumerate(pdf, start=1):
        text = page.get_text("text").strip()
        if text:
            documents.append(
                Document(
                    page_content=text,
                    metadata={"page": page_number, "section": f"Page {page_number}"},
                )
            )
    pdf.close()
    if not documents:
        raise ValueError("No readable text was found. Scanned PDFs require OCR before upload.")
    return title.strip(), documents


def _extract_epub(content: bytes, filename: str) -> tuple[str, list[Document]]:
    with NamedTemporaryFile(suffix=".epub", delete=True) as temporary:
        temporary.write(content)
        temporary.flush()
        book = epub.read_epub(temporary.name, options={"ignore_ncx": True})

    titles = book.get_metadata("DC", "title")
    title = titles[0][0] if titles else Path(filename).stem
    documents: list[Document] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        heading = soup.find(["h1", "h2", "h3"])
        section = heading.get_text(" ", strip=True) if heading else item.get_name()
        text = soup.get_text("\n", strip=True)
        if text:
            documents.append(Document(page_content=text, metadata={"section": section}))
    if not documents:
        raise ValueError("No readable chapters were found in this EPUB.")
    return str(title).strip(), documents


def _extract_text(content: bytes, filename: str) -> tuple[str, list[Document]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    if not text.strip():
        raise ValueError("The uploaded file is empty.")
    title = Path(filename).stem
    return title, [Document(page_content=text, metadata={"section": title})]
