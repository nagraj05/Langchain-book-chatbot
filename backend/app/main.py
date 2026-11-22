from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ingestion import SUPPORTED_SUFFIXES, extract_documents, split_documents
from app.library import content_id, registry
from app.rag import rag_service
from app.schemas import (
    Book,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    UploadResponse,
)

app = FastAPI(
    title="Local Library AI API",
    version="0.1.0",
    description="Local ebook ingestion and grounded question answering.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_ok = response.is_success
        except httpx.HTTPError:
            ollama_ok = False
    try:
        await asyncio.to_thread(rag_service.client.get_collections)
        qdrant_ok = True
    except Exception:  # noqa: BLE001 - transport exceptions vary by Qdrant client.
        qdrant_ok = False
    return HealthResponse(
        status="ok" if ollama_ok and qdrant_ok else "degraded",
        ollama=ollama_ok,
        qdrant=qdrant_ok,
        chat_model=settings.chat_model,
        embedding_model=settings.embedding_model,
    )


@app.get("/api/books", response_model=list[Book])
def list_books() -> list[Book]:
    return sorted(registry.list(), key=lambda book: book.added_at, reverse=True)


@app.post("/api/books/upload", response_model=UploadResponse)
async def upload_book(file: Annotated[UploadFile, File()]) -> UploadResponse:
    filename = file.filename or "book"
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail="Supported formats are PDF, EPUB, TXT, and Markdown.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum file size is 100 MB.")

    book_id = content_id(content)
    existing = registry.get(book_id)
    if existing:
        return UploadResponse(book=existing, already_indexed=True)

    try:
        title, documents = await asyncio.to_thread(extract_documents, content, filename)
        chunks = await asyncio.to_thread(split_documents, documents)
        if not chunks:
            raise ValueError("No readable text chunks were produced.")
        await asyncio.to_thread(rag_service.index, book_id, title, filename, chunks)
        book = registry.add(
            book_id=book_id,
            title=title,
            filename=filename,
            chunks=len(chunks),
        )
        return UploadResponse(book=book)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Indexing failed. Check that Ollama and Qdrant are running: {exc}",
        ) from exc


@app.delete("/api/books/{book_id}", status_code=204)
async def delete_book(book_id: str) -> None:
    if not registry.get(book_id):
        raise HTTPException(status_code=404, detail="Book not found.")
    await asyncio.to_thread(rag_service.remove, book_id)
    registry.remove(book_id)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not registry.list():
        raise HTTPException(status_code=400, detail="Upload a book first.")
    known_ids = {book.id for book in registry.list()}
    if request.book_ids and not set(request.book_ids).issubset(known_ids):
        raise HTTPException(status_code=400, detail="One or more books do not exist.")
    try:
        answer, sources = await asyncio.to_thread(
            rag_service.answer,
            request.question.strip(),
            request.book_ids,
            request.history,
        )
        return ChatResponse(answer=answer, sources=sources)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Answer generation failed. Check that Ollama and Qdrant are running: {exc}",
        ) from exc
