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

type Book = { id: string; title: string; filename: string; file_type: string; chunks: number; added_at: string };
type Source = { index: number; book_id: string; title: string; section?: string; page?: number; excerpt: string };
type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };
type UploadPhase = "idle" | "indexing" | "done" | "error";
type ConversationSummary = {
  id: string;
  title: string;
  book_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};
type ConversationDetail = ConversationSummary & { messages: (Message & { created_at: string })[] };
type DeleteTarget = { kind: "book" | "conversation"; id: string; title: string };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function fallbackSuggestions(title: string): string[] {
  return [
    `What is ${title} mainly about?`,
    "What are the most important ideas in this document?",
    "What should I understand first?",
  ];
}

function formatRelativeTime(value: string): string {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.floor(elapsed / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function PlusIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 4v12M4 10h12" /></svg>;
}

function ChevronIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6.5 8 3.5 3.5L13.5 8" /></svg>;
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3.75h6.5L18.25 8.5v11.75H7z" />
      <path d="M13.5 3.75V8.5h4.75M9.5 13h6M9.5 16h4.5" />
    </svg>
  );
}

function SendIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4 10 11-5-3.8 10-1.7-3.5z" /></svg>;
}

function MenuIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 6h12M4 10h12M4 14h12" /></svg>;
}

function SearchIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="9" cy="9" r="5" /><path d="m13 13 3 3" /></svg>;
}

function TrashIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 6.5h8M8 6.5V5h4v1.5M7 8.5l.5 6h5l.5-6" /></svg>;
}

export default function Home() {
  const [books, setBooks] = useState<Book[]>([]);
  const [selectedBooks, setSelectedBooks] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historyQuery, setHistoryQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>("idle");
  const [uploadName, setUploadName] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const deleteCancelButton = useRef<HTMLButtonElement>(null);
  const scopeMenu = useRef<HTMLDivElement>(null);
  const endOfChat = useRef<HTMLDivElement>(null);

  const loadBooks = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/books`);
    if (!response.ok) throw new Error("Could not load the local library.");
    const loadedBooks: Book[] = await response.json();
    setBooks(loadedBooks);
    setSelectedBooks((current) => {
      const activeBook = loadedBooks.find((book) => book.id === current[0]);
      if (activeBook) return [activeBook.id];
      return loadedBooks[0] ? [loadedBooks[0].id] : [];
    });
  }, []);

  const loadConversations = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/conversations`);
    if (!response.ok) throw new Error("Could not load conversation history.");
    setConversations(await response.json());
  }, []);

  useEffect(() => {
    void loadBooks().catch((error) => setNotice(errorMessage(error)));
    void loadConversations().catch((error) => setNotice(errorMessage(error)));
  }, [loadBooks, loadConversations]);

  useEffect(() => {
    endOfChat.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  useEffect(() => {
    if (deleteTarget) deleteCancelButton.current?.focus();
  }, [deleteTarget]);

  useEffect(() => {
    function closeScope(event: MouseEvent) {
      if (!scopeMenu.current?.contains(event.target as Node)) setScopeOpen(false);
    }
    document.addEventListener("mousedown", closeScope);
    return () => document.removeEventListener("mousedown", closeScope);
  }, []);

  useEffect(() => {
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      setScopeOpen(false);
      setDrawerOpen(false);
      if (!deletePending) setDeleteTarget(null);
      if (uploadPhase !== "indexing") setUploadOpen(false);
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [deletePending, uploadPhase]);

  function openUpload() {
    setUploadPhase("idle");
    setUploadName("");
    setUploadError("");
    setUploadOpen(true);
  }

  function closeUpload() {
    if (uploadPhase !== "indexing") setUploadOpen(false);
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadName(file.name);
    setUploadError("");
    setUploadPhase("indexing");
    setNotice(null);

    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${API_URL}/api/books/upload`, { method: "POST", body });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Upload failed.");
      await loadBooks();
      setSelectedBooks([result.book.id]);
      setActiveConversationId(null);
      setMessages([]);
      setQuestion("");
      setUploadName(result.book.title);
      setUploadPhase("done");
    } catch (error) {
      setUploadError(errorMessage(error));
      setUploadPhase("error");
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  function selectBook(bookId: string) {
    if (selectedBooks[0] !== bookId) {
      setActiveConversationId(null);
      setMessages([]);
      setQuestion("");
    }
    setSelectedBooks([bookId]);
    setScopeOpen(false);
  }

  function requestBookDeletion(book: Book) {
    setScopeOpen(false);
    setDeleteError("");
    setDeleteTarget({ kind: "book", id: book.id, title: book.title });
  }

  function startNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setQuestion("");
    setNotice(null);
    setDrawerOpen(false);
  }

  async function openConversation(conversationId: string) {
    setNotice(null);
    try {
      const response = await fetch(`${API_URL}/api/conversations/${conversationId}`);
      if (!response.ok) throw new Error("Could not open that conversation.");
      const conversation: ConversationDetail = await response.json();
      setActiveConversationId(conversation.id);
      setSelectedBooks([conversation.book_id]);
      setMessages(conversation.messages.map(({ role, content, sources }) => ({ role, content, sources })));
      setQuestion("");
      setDrawerOpen(false);
    } catch (error) {
      setNotice(errorMessage(error));
    }
  }

  function requestConversationDeletion(conversation: ConversationSummary) {
    setDeleteError("");
    setDeleteTarget({ kind: "conversation", id: conversation.id, title: conversation.title });
  }

  function closeDeleteModal() {
    if (!deletePending) setDeleteTarget(null);
  }

  async function confirmDeletion() {
    if (!deleteTarget || deletePending) return;
    setDeletePending(true);
    setDeleteError("");
    setNotice(null);
    try {
      if (deleteTarget.kind === "book") {
        const response = await fetch(`${API_URL}/api/books/${deleteTarget.id}`, {
          method: "DELETE",
        });
        if (!response.ok) throw new Error("Could not delete that book.");
        if (selectedBooks[0] === deleteTarget.id) {
          setActiveConversationId(null);
          setMessages([]);
          setQuestion("");
        }
        await Promise.all([loadBooks(), loadConversations()]);
        setNotice(`${deleteTarget.title} was deleted from this device.`);
      } else {
        const response = await fetch(`${API_URL}/api/conversations/${deleteTarget.id}`, {
          method: "DELETE",
        });
        if (!response.ok) throw new Error("Could not delete that conversation.");
        if (activeConversationId === deleteTarget.id) startNewChat();
        await loadConversations();
      }
      setDeleteTarget(null);
    } catch (error) {
      setDeleteError(errorMessage(error));
    } finally {
      setDeletePending(false);
    }
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
      let conversationId = activeConversationId;
      if (!conversationId) {
        if (!selectedBook) throw new Error("Select a book first.");
        const createResponse = await fetch(`${API_URL}/api/conversations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            book_id: selectedBook.id,
            title: cleanQuestion.length > 64 ? `${cleanQuestion.slice(0, 61)}…` : cleanQuestion,
          }),
        });
        const created = await createResponse.json();
        if (!createResponse.ok) throw new Error(created.detail ?? "Could not start a conversation.");
        conversationId = created.id;
        setActiveConversationId(conversationId);
      }

      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: cleanQuestion,
          book_ids: selectedBooks,
          history: priorMessages.slice(-6).map(({ role, content }) => ({ role, content })),
          conversation_id: conversationId,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "The model could not answer.");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.answer, sources: result.sources },
      ]);
      await loadConversations();
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: `I couldn't complete that request. ${errorMessage(error)}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const selectedBook = books.find((book) => book.id === selectedBooks[0]);
  const scopeLabel = selectedBook?.title ?? "Select a book";

  useEffect(() => {
    if (!selectedBook) {
      setSuggestions([]);
      setSuggestionsLoading(false);
      return;
    }

    const controller = new AbortController();
    setSuggestions([]);
    setSuggestionsLoading(true);
    void fetch(`${API_URL}/api/books/${selectedBook.id}/suggestions`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail ?? "Could not generate suggestions.");
        return result.suggestions as string[];
      })
      .then((generated) => setSuggestions(generated))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setSuggestions(fallbackSuggestions(selectedBook.title));
      })
      .finally(() => {
        if (!controller.signal.aborted) setSuggestionsLoading(false);
      });

    return () => controller.abort();
  }, [selectedBook]);

  const filteredConversations = conversations.filter((conversation) => {
    const bookTitle = books.find((book) => book.id === conversation.book_id)?.title ?? "";
    const query = historyQuery.trim().toLowerCase();
    return !query || conversation.title.toLowerCase().includes(query) || bookTitle.toLowerCase().includes(query);
  });

  return (
    <main className="workspace">
      <button
        className={`drawer-backdrop ${drawerOpen ? "visible" : ""}`}
        onClick={() => setDrawerOpen(false)}
        aria-label="Close conversation history"
        tabIndex={drawerOpen ? 0 : -1}
      />

      <aside className={`history-drawer ${drawerOpen ? "open" : ""}`} aria-hidden={!drawerOpen}>
        <div className="drawer-header">
          <strong>Conversations</strong>
          <button onClick={() => setDrawerOpen(false)} aria-label="Close conversation history">×</button>
        </div>
        <button className="drawer-new-chat" onClick={startNewChat}><PlusIcon /> New chat</button>
        <label className="history-search">
          <SearchIcon />
          <input
            value={historyQuery}
            onChange={(event) => setHistoryQuery(event.target.value)}
            placeholder="Search conversations"
          />
        </label>
        <div className="history-list">
          {filteredConversations.length === 0 ? (
            <div className="history-empty">
              <span>{conversations.length ? "No matching conversations" : "No conversations yet"}</span>
              <p>Your chats will be saved locally and appear here.</p>
            </div>
          ) : filteredConversations.map((conversation) => {
            const bookTitle = books.find((book) => book.id === conversation.book_id)?.title ?? "Book unavailable";
            const active = conversation.id === activeConversationId;
            return (
              <div className={`history-item ${active ? "active" : ""}`} key={conversation.id}>
                <button className="history-open" onClick={() => void openConversation(conversation.id)}>
                  <strong>{conversation.title}</strong>
                  <span>{bookTitle} · {formatRelativeTime(conversation.updated_at)}</span>
                </button>
                <button
                  className="history-delete"
                  onClick={() => requestConversationDeletion(conversation)}
                  aria-label={`Delete ${conversation.title}`}
                ><TrashIcon /></button>
              </div>
            );
          })}
        </div>
        <div className="drawer-footer"><span className="privacy-dot" /> Stored only on this device</div>
      </aside>

      <header className="topbar">
        <div className="header-brand">
          <button className="menu-button" onClick={() => setDrawerOpen(true)} aria-label="Open conversation history">
            <MenuIcon />
          </button>
          <div className="brand-lockup">
            <img src="/icon.svg" alt="" />
            <strong className="brand-name"><span>BOOK</span><span>Bot</span></strong>
          </div>
        </div>

        <div className="header-scope">
          <div className="scope-picker" ref={scopeMenu}>
            <button
              className="scope-trigger"
              onClick={() => setScopeOpen((current) => !current)}
              aria-expanded={scopeOpen}
              aria-haspopup="menu"
            >
              <span className="scope-icon"><FileIcon /></span>
              <span className="scope-label">{scopeLabel}</span>
              <ChevronIcon />
            </button>

            {scopeOpen && (
              <div className="scope-popover" role="menu">
                <div className="scope-popover-header">
                  <div><strong>Choose a book</strong><span>Select or remove an indexed file</span></div>
                </div>
                <div className="scope-options">
                  {books.length === 0 ? (
                    <div className="scope-empty">
                      <FileIcon /><span>No indexed books yet</span>
                      <button onClick={() => { setScopeOpen(false); openUpload(); }}>Add your first file</button>
                    </div>
                  ) : books.map((book) => {
                    const selected = selectedBooks[0] === book.id;
                    return (
                      <div className="scope-option-row" role="none" key={book.id}>
                        <button
                          className={`scope-option ${selected ? "selected" : ""}`}
                          role="menuitemradio"
                          aria-checked={selected}
                          onClick={() => selectBook(book.id)}
                        >
                          <span className="custom-check" aria-hidden="true">✓</span>
                          <span className="scope-book-copy">
                            <strong>{book.title}</strong>
                            <span>{book.file_type.toUpperCase()} · {book.chunks} passages</span>
                          </span>
                        </button>
                        <button
                          className="scope-delete"
                          onClick={() => requestBookDeletion(book)}
                          aria-label={`Delete ${book.title}`}
                        ><TrashIcon /></button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="topbar-actions">
          <button className="add-file-button" onClick={openUpload}><PlusIcon /><span>Add file</span></button>
        </div>
      </header>

      <section className="chat-stage">
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
                <div className="empty-mark"><img src="/icon.svg" alt="" /></div>
                <h1>
                  What would you like to know
                  {selectedBook ? <> in <span>{selectedBook.title}</span></> : ""}?
                </h1>
                <p className="empty-copy">
                  Ask questions across your books and get clear answers with the exact source passages attached.
                </p>
                {books.length > 0 ? (
                  suggestionsLoading ? (
                    <div className="suggestion-skeletons" aria-label="Generating suggested questions">
                      <span /><span /><span />
                    </div>
                  ) : (
                    <div className="suggestions">
                      {suggestions.map((suggestion) => (
                        <button key={suggestion} onClick={() => setQuestion(suggestion)}>{suggestion}</button>
                      ))}
                    </div>
                  )
                ) : (
                  <button className="empty-add-button" onClick={openUpload}><PlusIcon /> Add your first book</button>
                )}
              </div>
            ) : messages.map((message, index) => (
              <article className={`message-row ${message.role}`} key={`${message.role}-${index}`}>
                <div className="avatar" aria-hidden="true">{message.role === "user" ? "You" : "L"}</div>
                <div className="message-content">
                  <div className="message-author">{message.role === "user" ? "You" : "BOOKBot"}</div>
                  <div className="message-text">
                    {message.role === "assistant" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    ) : message.content}
                  </div>
                  {message.sources && message.sources.length > 0 && (
                    <details className="sources">
                      <summary>{message.sources.length} source passages</summary>
                      <div className="source-list">
                        {message.sources.map((source) => (
                          <div className="source-card" key={`${index}-${source.index}`}>
                            <div className="source-title">
                              <strong>[{source.index}] {source.title}</strong>
                              <span>{source.section}{source.page ? ` · Page ${source.page}` : ""}</span>
                            </div>
                            <p>{source.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </article>
            ))}

            {busy && (
              <div className="message-row assistant loading-row">
                <div className="avatar" aria-hidden="true">L</div>
                <div className="message-content">
                  <div className="message-author">BOOKBot</div>
                  <div className="typing-indicator" aria-label="Generating answer"><span /><span /><span /></div>
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
              placeholder={selectedBook ? `Ask about ${selectedBook.title}…` : "Add a book to begin"}
              disabled={busy || !selectedBook}
              rows={1}
              aria-label="Message"
            />
            <button
              className="send-button"
              type="submit"
              disabled={!question.trim() || busy || !selectedBook}
              aria-label="Send message"
            ><SendIcon /></button>
          </form>
          <div className="composer-helper">
            <span>Enter to send · Shift + Enter for a new line</span>
            <span>Answers are generated locally and may contain mistakes.</span>
          </div>
        </footer>
      </section>

      {deleteTarget && (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeDeleteModal}>
          <section
            className="delete-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            aria-describedby="delete-description"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="delete-modal-icon" aria-hidden="true"><TrashIcon /></div>
            <h2 id="delete-title">
              {deleteTarget.kind === "book" ? "Delete this book?" : "Delete this conversation?"}
            </h2>
            <p className="delete-target-name">{deleteTarget.title}</p>
            <p id="delete-description" className="delete-description">
              {deleteTarget.kind === "book"
                ? "Its local index, generated suggestions, and related conversations will be permanently removed from this device."
                : "Its messages and source citations will be permanently removed. The indexed book will remain available."}
            </p>
            {deleteError && <p className="delete-error" role="alert">{deleteError}</p>}
            <div className="delete-actions">
              <button
                ref={deleteCancelButton}
                className="delete-cancel"
                onClick={closeDeleteModal}
                disabled={deletePending}
              >Cancel</button>
              <button className="delete-confirm" onClick={() => void confirmDeletion()} disabled={deletePending}>
                {deletePending ? "Deleting…" : deleteTarget.kind === "book" ? "Delete book" : "Delete chat"}
              </button>
            </div>
          </section>
        </div>
      )}

      {uploadOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeUpload}>
          <section
            className="upload-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button
              className="modal-close"
              onClick={closeUpload}
              disabled={uploadPhase === "indexing"}
              aria-label="Close upload dialog"
            >×</button>

            {uploadPhase === "idle" && (
              <>
                <div className="modal-icon"><FileIcon /></div>
                <p className="modal-eyebrow">Add to your library</p>
                <h2 id="upload-title">Upload a book</h2>
                <p className="modal-description">
                  Your file is processed locally, split into passages, and indexed for search.
                </p>
                <button className="file-dropzone" onClick={() => fileInput.current?.click()}>
                  <span className="dropzone-icon"><PlusIcon /></span>
                  <strong>Choose a file</strong>
                  <span>PDF, EPUB, TXT or Markdown · up to 100 MB</span>
                </button>
              </>
            )}

            {uploadPhase === "indexing" && (
              <div className="upload-state">
                <div className="indexing-orbit" aria-hidden="true"><span /><span /><span /><FileIcon /></div>
                <p className="modal-eyebrow">Building your index</p>
                <h2 id="upload-title">Uploading and indexing</h2>
                <p className="upload-file-name">{uploadName}</p>
                <div className="indeterminate-progress"><span /></div>
                <p className="upload-helper">Extracting text, creating embeddings, and saving passages locally.</p>
              </div>
            )}

            {uploadPhase === "done" && (
              <div className="upload-state">
                <div className="success-mark" aria-hidden="true">✓</div>
                <p className="modal-eyebrow">Index complete</p>
                <h2 id="upload-title">Your book is ready</h2>
                <p className="upload-file-name">{uploadName}</p>
                <p className="upload-helper">It has been selected for your next question.</p>
                <button className="modal-primary" onClick={closeUpload}>Start chatting</button>
              </div>
            )}

            {uploadPhase === "error" && (
              <div className="upload-state">
                <div className="error-mark" aria-hidden="true">!</div>
                <p className="modal-eyebrow">Upload failed</p>
                <h2 id="upload-title">We couldn’t index that file</h2>
                <p className="upload-error">{uploadError}</p>
                <button className="modal-primary" onClick={() => setUploadPhase("idle")}>Try another file</button>
              </div>
            )}

            <input
              ref={fileInput}
              className="visually-hidden"
              type="file"
              accept=".pdf,.epub,.txt,.md"
              onChange={upload}
            />
          </section>
        </div>
      )}
    </main>
  );
}
