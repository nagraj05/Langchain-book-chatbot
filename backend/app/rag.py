from __future__ import annotations

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

        results = store.similarity_search_with_score(question, k=8, filter=query_filter)
        if not results:
            return (
                "I couldn't find relevant passages in the selected books.",
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
        system_prompt = (
            "You answer questions about the user's private library. Use only the "
            "provided source passages. If the passages do not establish an answer, "
            "say that you could not find it in the selected books. Do not invent "
            "characters, events, quotations, chapters, or page numbers. Cite factual "
            "claims using [1], [2], etc., matching the source number. Give a direct, "
            "clear answer and distinguish facts from interpretation."
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


def _excerpt(text: str, limit: int = 320) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rsplit(" ", 1)[0] + "…"


rag_service = RagService()
