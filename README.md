# Local Library AI

A completely local RAG application for asking grounded questions about PDF, EPUB, TXT, and Markdown books.

## Stack

- Next.js frontend
- FastAPI backend
- LangChain with Ollama
- Qdrant vector database
- `qwen3.5:9b` for answers
- `qwen3-embedding:0.6b` for embeddings

No book text is sent to a hosted AI service.

## Prerequisites

- Ollama running with the two models above
- Docker Desktop
- Python 3.12+
- Node.js 20+
- uv
- Bun

## Start the application

### 1. Start Qdrant

```powershell
docker compose up -d qdrant
```

The Qdrant dashboard is available at <http://localhost:6333/dashboard>.

### 2. Start the backend

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

API documentation is available at <http://localhost:8000/docs>.

### 3. Start the frontend

In another PowerShell window:

```powershell
cd frontend
bun install
bun run dev
```

Open <http://localhost:3000>.

## Configuration

Copy `backend/.env.example` to `backend/.env` if you want to change model names or service URLs. The backend defaults work with the included Docker Compose service and a standard Ollama installation.

For the frontend, create `frontend/.env.local` only if the API is not at `http://localhost:8000`:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Privacy note

The application is local by default. Do not enable LangSmith tracing if book content must never leave the computer. The included project does not configure LangSmith or Pinecone.

