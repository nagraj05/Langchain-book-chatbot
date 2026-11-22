"use client";

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Book = {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  chunks: number;
  added_at: string;
};

type Source = {
  index: number;
  book_id: string;
  title: string;
  section?: string;
  page?: number;
  excerpt: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

type Health = {
  status: "ok" | "degraded";
  ollama: boolean;
  qdrant: boolean;
  chat_model: string;
};

const SUGGESTIONS = [
  "Summarize the central conflict",
  "Who are the main characters?",
  "What themes appear repeatedly?",
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export default function Home() {
  const [books, setBooks] = useState<Book[]>([]);
  const [selectedBooks, setSelectedBooks] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const endOfChat = useRef<HTMLDivElement>(null);

  const loadBooks = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/books`);
    if (!response.ok) throw new Error("Could not load the local library.");
    setBooks(await response.json());
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      if (!response.ok) throw new Error();
      setHealth(await response.json());
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    void loadBooks().catch((error) => setNotice(errorMessage(error)));
    void checkHealth();
  }, [checkHealth, loadBooks]);

  useEffect(() => {
    endOfChat.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setNotice(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${API_URL}/api/books/upload`, {
        method: "POST",
        body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Upload failed.");
      await loadBooks();
      setSelectedBooks([result.book.id]);
      setNotice(
        result.already_indexed
          ? "This book is already in your library."
          : `${result.book.title} is ready.`,
      );
      setLibraryOpen(false);
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removeBook(book: Book) {
    if (!window.confirm(`Remove “${book.title}” from the local index?`)) return;
    setNotice(null);
    try {
      const response = await fetch(`${API_URL}/api/books/${book.id}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Could not remove the book.");
      setSelectedBooks((current) => current.filter((id) => id !== book.id));
      await loadBooks();
    } catch (error) {
      setNotice(errorMessage(error));
    }
  }

  function toggleBook(bookId: string) {
    setSelectedBooks((current) =>
      current.includes(bookId)
        ? current.filter((id) => id !== bookId)
        : [...current, bookId],
    );
  }

  function resetChat() {
    setMessages([]);
    setQuestion("");
    setNotice(null);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (!cleanQuestion || busy) return;

    const userMessage: Message = { role: "user", content: cleanQuestion };
    const priorMessages = messages;
    setMessages([...messages, userMessage]);
    setQuestion("");
    setBusy(true);
    setNotice(null);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: cleanQuestion,
          book_ids: selectedBooks,
          history: priorMessages
            .slice(-6)
            .map(({ role, content }) => ({ role, content })),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "The model could not answer.");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.answer, sources: result.sources },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `I couldn't complete that request. ${errorMessage(error)}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const scopeLabel = selectedBooks.length
    ? `${selectedBooks.length} selected ${selectedBooks.length === 1 ? "book" : "books"}`
    : "All books";

  return (
    <div className="app-shell">
      <button
        className={`drawer-overlay ${libraryOpen ? "visible" : ""}`}
        aria-label="Close library"
        onClick={() => setLibraryOpen(false)}
      />

      <aside className={`sidebar ${libraryOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">L</span>
            <div>
              <strong>Local Library</strong>
              <span>Private book assistant</span>
            </div>
          </div>
          <button
            className="icon-button close-drawer"
            onClick={() => setLibraryOpen(false)}
            aria-label="Close library"
          >
            ×
          </button>
        </div>

        <button
          className="new-chat-button"
          onClick={resetChat}
          disabled={messages.length === 0}
        >
          New conversation
        </button>

        <div className="library-title">
          <span>Library</span>
          <span>{books.length}</span>
        </div>

        <div className="book-list">
          {books.length === 0 ? (
            <div className="empty-library">
              <strong>No books yet</strong>
              <span>Add a PDF or EPUB to get started.</span>
            </div>
          ) : (
            books.map((book) => {
              const selected = selectedBooks.includes(book.id);
              return (
                <div className={`book-item ${selected ? "selected" : ""}`} key={book.id}>
                  <button
                    className="book-select"
                    onClick={() => toggleBook(book.id)}
                    aria-pressed={selected}
                  >
                    <span className="file-badge">{book.file_type.toUpperCase()}</span>
                    <span className="book-details">
                      <strong>{book.title}</strong>
                      <span>{book.chunks} passages</span>
                    </span>
                    <span className="selection-mark" aria-hidden="true">
                      {selected ? "✓" : ""}
                    </span>
                  </button>
                  <button
                    className="remove-book"
                    onClick={() => void removeBook(book)}
                    aria-label={`Remove ${book.title}`}
                  >
                    ×
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="sidebar-footer">
          <button
            className="add-book-button"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Indexing book…" : "Add book"}
          </button>
          <input
            ref={fileInput}
            className="visually-hidden"
            type="file"
            accept=".pdf,.epub,.txt,.md"
            onChange={upload}
          />
          <span className="file-hint">PDF, EPUB, TXT or MD · 100 MB max</span>
        </div>
      </aside>

      <main className="chat-shell">
        <header className="chat-header">
          <div className="chat-heading">
            <button
              className="icon-button open-drawer"
              onClick={() => setLibraryOpen(true)}
              aria-label="Open library"
            >
              ☰
            </button>
            <div>
              <h1>Chat with your library</h1>
              <span>{scopeLabel}</span>
            </div>
          </div>
          <div className={`service-status ${health?.status === "ok" ? "online" : ""}`}>
            <span className="status-dot" />
            <span>{health?.status === "ok" ? "Local models ready" : "Services offline"}</span>
          </div>
        </header>

        {notice && (
          <div className="notice" role="status">
            <span>{notice}</span>
            <button onClick={() => setNotice(null)} aria-label="Dismiss message">×</button>
          </div>
        )}

        <section className="conversation" aria-live="polite">
          <div className="conversation-inner">
            {messages.length === 0 ? (
              <div className="empty-chat">
                <div className="empty-icon" aria-hidden="true">L</div>
                <h2>Ask your books anything</h2>
                <p>
                  Get answers grounded in your local library, with the source passages
                  included.
                </p>
                <div className="suggestions">
                  {SUGGESTIONS.map((suggestion) => (
                    <button key={suggestion} onClick={() => setQuestion(suggestion)}>
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <article className={`message-row ${message.role}`} key={`${message.role}-${index}`}>
                  <div className="avatar" aria-hidden="true">
                    {message.role === "user" ? "You" : "L"}
                  </div>
                  <div className="message-content">
                    <div className="message-author">
                      {message.role === "user" ? "You" : "Local Library"}
                    </div>
                    <div className="message-text">
                      {message.role === "assistant" ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {message.content}
                        </ReactMarkdown>
                      ) : (
                        message.content
                      )}
                    </div>
                    {message.sources && message.sources.length > 0 && (
                      <details className="sources">
                        <summary>{message.sources.length} source passages</summary>
                        <div className="source-list">
                          {message.sources.map((source) => (
                            <div className="source-card" key={`${index}-${source.index}`}>
                              <div className="source-title">
                                <strong>[{source.index}] {source.title}</strong>
                                <span>
                                  {source.section}
                                  {source.page ? ` · Page ${source.page}` : ""}
                                </span>
                              </div>
                              <p>{source.excerpt}</p>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </article>
              ))
            )}

            {busy && (
              <div className="message-row assistant loading-row">
                <div className="avatar" aria-hidden="true">L</div>
                <div className="message-content">
                  <div className="message-author">Local Library</div>
                  <div className="typing-indicator" aria-label="Generating answer">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
            <div ref={endOfChat} />
          </div>
        </section>

        <footer className="composer-area">
          <form className="composer" onSubmit={ask}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder={books.length ? "Ask about your books…" : "Add a book to begin"}
              disabled={busy || books.length === 0}
              rows={1}
              aria-label="Message"
            />
            <button
              className="send-button"
              type="submit"
              disabled={!question.trim() || busy || books.length === 0}
            >
              Send
            </button>
          </form>
          <div className="composer-meta">
            <span>{scopeLabel}</span>
            <span>Enter to send · Shift + Enter for a new line</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
