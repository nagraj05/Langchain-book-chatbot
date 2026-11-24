import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    chat_model: str = os.getenv("CHAT_MODEL", "qwen3.5:9b")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "ebook_chunks")
    retrieval_score_threshold: float = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.28"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    data_dir: Path = BACKEND_DIR / "data"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
