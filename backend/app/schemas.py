from typing import Literal

from pydantic import BaseModel, Field


class Book(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    chunks: int
    added_at: str


class UploadResponse(BaseModel):
    book: Book
    already_indexed: bool = False


class SuggestionsResponse(BaseModel):
    book_id: str
    suggestions: list[str]
    cached: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    book_ids: list[str] = Field(default_factory=list)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    conversation_id: str | None = None


class Source(BaseModel):
    index: int
    book_id: str
    title: str
    section: str | None = None
    page: int | None = None
    excerpt: str
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


class ConversationCreate(BaseModel):
    book_id: str
    title: str = Field(min_length=1, max_length=120)


class ConversationSummary(BaseModel):
    id: str
    title: str
    book_id: str
    created_at: str
    updated_at: str
    message_count: int


class StoredMessage(ChatMessage):
    sources: list[Source] = Field(default_factory=list)
    created_at: str


class ConversationDetail(ConversationSummary):
    messages: list[StoredMessage]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    ollama: bool
    qdrant: bool
    chat_model: str
    embedding_model: str
