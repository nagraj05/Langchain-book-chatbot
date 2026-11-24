from __future__ import annotations

import json
import re
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from app.config import settings
from app.schemas import ChatMessage, Source


class RagService:
    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.qdrant_url, timeout=30)
        self.embeddings = OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
        )
        self.chat = ChatOllama(
            model=settings.chat_model,
            base_url=settings.ollama_base_url,
            reasoning=False,
            temperature=0.1,
            num_ctx=8192,
            num_predict=500,
            keep_alive="10m",
        )
        self._store: QdrantVectorStore | None = None

    def ensure_store(self) -> QdrantVectorStore:
        if self._store is not None:
            return self._store
        if not self.client.collection_exists(settings.qdrant_collection):
            vector_size = len(self.embeddings.embed_query("dimension probe"))
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )
        self._store = QdrantVectorStore(
            client=self.client,
            collection_name=settings.qdrant_collection,
            embedding=self.embeddings,
        )
        return self._store

    def index(self, book_id: str, title: str, filename: str, chunks: list[Document]) -> None:
        store = self.ensure_store()
        for index, chunk in enumerate(chunks):
            chunk.metadata.update(
                {
                    "book_id": book_id,
                    "title": title,
                    "filename": filename,
                    "chunk_index": index,
                }
            )
        store.add_documents(chunks, ids=[uuid4().hex for _ in chunks])

    def remove(self, book_id: str) -> None:
        if not self.client.collection_exists(settings.qdrant_collection):
            return
        self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.book_id",
                            match=models.MatchValue(value=book_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def answer(
        self, question: str, book_ids: list[str], history: list[ChatMessage]
    ) -> tuple[str, list[Source]]:
        casual_answer = _casual_response(question)
        if casual_answer:
            return casual_answer, []

        store = self.ensure_store()
        query_filter = None
        if book_ids:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.book_id",
                        match=models.MatchAny(any=book_ids),
                    )
                ]
            )

        results = store.similarity_search_with_score(
            question,
            k=8,
            filter=query_filter,
            score_threshold=settings.retrieval_score_threshold,
        )
        if not results:
            return (
                (
                    "I couldn't find relevant information about that in the selected book. "
                    "Try asking a more specific question about its content."
                ),
                [],
            )

        context_blocks: list[str] = []
        sources: list[Source] = []
        for index, (document, score) in enumerate(results, start=1):
            metadata = document.metadata
            context_blocks.append(
                f"[SOURCE {index}]\n"
                f"Book: {metadata.get('title', 'Unknown')}\n"
                f"Section: {metadata.get('section', 'Unknown')}\n"
                f"Page: {metadata.get('page', 'N/A')}\n"
                f"Passage: {document.page_content}"
            )
            sources.append(
                Source(
                    index=index,
                    book_id=str(metadata.get("book_id", "")),
                    title=str(metadata.get("title", "Unknown")),
                    section=metadata.get("section"),
                    page=metadata.get("page"),
                    excerpt=_excerpt(document.page_content),
                    score=round(float(score), 4),
                )
            )

        history_text = "\n".join(
            f"{message.role.title()}: {message.content}" for message in history[-6:]
        )
        valid_citations = f"[1] through [{len(sources)}]"
        system_prompt = (
            "You answer questions about the user's private library. Use only the "
            "provided source passages. If the passages do not establish an answer, "
            "say that you could not find it in the selected books. Do not invent "
            "characters, events, quotations, chapters, or page numbers. Cite factual "
            f"claims using only {valid_citations}, matching the source number. Never "
            "cite a number outside that range. Answer the user's actual question; do "
            "not summarize unrelated passages. Give a direct, clear answer and "
            "distinguish facts from interpretation."
        )
        user_prompt = (
            f"Recent conversation:\n{history_text or '(none)'}\n\n"
            f"Source passages:\n\n{'\n\n'.join(context_blocks)}\n\n"
            f"Question: {question}"
        )
        response = self.chat.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        return str(response.content), sources

    def suggest_questions(self, book_id: str, title: str) -> list[str]:
        if not self.client.collection_exists(settings.qdrant_collection):
            raise ValueError("The book index is not available.")

        points, _ = self.client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.book_id",
                        match=models.MatchValue(value=book_id),
                    )
                ]
            ),
            limit=60,
            with_payload=True,
            with_vectors=False,
        )
        passages: list[tuple[int, str]] = []
        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}
            text = str(payload.get("page_content") or "").strip()
            if text:
                passages.append((int(metadata.get("chunk_index", len(passages))), text))
        passages.sort(key=lambda item: item[0])
        if not passages:
            raise ValueError("No indexed passages were found for this book.")

        sample_count = min(6, len(passages))
        if sample_count == 1:
            sample_indices = [0]
        else:
            sample_indices = sorted(
                {round(index * (len(passages) - 1) / (sample_count - 1)) for index in range(sample_count)}
            )
        excerpts = "\n\n".join(
            f"[Excerpt {position + 1}]\n{passages[index][1][:900]}"
            for position, index in enumerate(sample_indices)
        )
        response = self.chat.invoke(
            [
                SystemMessage(
                    content=(
                        "Generate exactly three useful questions a reader could ask about the "
                        "provided document. Make them specific to its actual content, varied, and "
                        "short enough for suggestion buttons. Do not assume the document is fiction. "
                        "Return only a JSON array of three strings."
                    )
                ),
                HumanMessage(content=f"Document title: {title}\n\n{excerpts}"),
            ]
        )
        return _parse_suggestions(str(response.content))


def _excerpt(text: str, limit: int = 320) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rsplit(" ", 1)[0] + "…"


def _casual_response(question: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9\s']", "", question.lower()).strip()
    normalized = " ".join(normalized.split())
    greetings = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
    }
    thanks = {"thanks", "thank you", "thank you so much", "thx"}
    farewells = {"bye", "goodbye", "see you", "see you later"}
    capabilities = {
        "what can you do",
        "how can you help",
        "who are you",
        "what are you",
    }
    if normalized in greetings:
        return "Hi! I'm **BOOKBot**. Ask me anything about the selected book."
    if normalized in thanks:
        return "You're welcome! Ask another question whenever you're ready."
    if normalized in farewells:
        return "Goodbye! Your book and conversation history will stay saved locally."
    if normalized in capabilities:
        return (
            "I'm **BOOKBot**. I answer questions about the selected book using its "
            "indexed passages and include source citations when the book supports the answer."
        )
    return None


def _parse_suggestions(content: str) -> list[str]:
    candidates: list[str] = []
    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                candidates = [str(item) for item in parsed]
        except json.JSONDecodeError:
            candidates = []
    if not candidates:
        candidates = [
            re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip(" \t\"'")
            for line in content.splitlines()
            if line.strip()
        ]

    suggestions: list[str] = []
    for candidate in candidates:
        clean = " ".join(candidate.split()).strip()
        if 8 <= len(clean) <= 140 and clean not in suggestions:
            suggestions.append(clean)
        if len(suggestions) == 3:
            break
    if len(suggestions) != 3:
        raise ValueError("The model did not return three valid suggestions.")
    return suggestions


rag_service = RagService()
