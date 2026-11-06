"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type { ChatResponse, Citation, DocumentItem } from "@/lib/types";
import { ColdStartStatus } from "./cold-start-status";

const CHAT_MAX_QUESTION_CHARS = 2000;
const CHAT_REQUEST_TIMEOUT_MS = 45_000;
const NOT_FOUND_ANSWER = "I could not find this in your documents.";

type Turn = {
  index: number;
  question: string;
  documentIds: string[];
  response?: ChatResponse;
  error?: string;
  retryable?: boolean;
  isLoading?: boolean;
};

function isNotFound(response: ChatResponse): boolean {
  return response.answer.trim() === NOT_FOUND_ANSWER && response.citations.length === 0;
}

function citationId(turnIndex: number, number: number): string {
  return `chat-citation-${turnIndex}-${number}`;
}

function NoticeIcon({ kind }: { kind: "error" | "warning" | "info" }) {
  const paths = {
    error: <><circle cx="12" cy="12" r="9" /><path d="m9 9 6 6m0-6-6 6" /></>,
    warning: <><path d="m12 3 10 18H2L12 3Z" /><path d="M12 9v4m0 3h.01" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8h.01" /></>,
  };
  return (
    <svg aria-hidden="true" className="notice-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      {paths[kind]}
    </svg>
  );
}

function friendlyChatError(error: unknown): { message: string; retryable: boolean } {
  if (!(error instanceof ApiError)) {
    return {
      message: "Something went wrong. Please try again.",
      retryable: true,
    };
  }
  if (error.status === 401) {
    return { message: "Your session expired. Please log in again.", retryable: false };
  }
  if (error.status === 422) {
    return {
      message:
        error.code === "QUESTION_TOO_LONG"
          ? `Questions must be ${CHAT_MAX_QUESTION_CHARS} characters or shorter.`
          : "Please check your question and try again.",
      retryable: false,
    };
  }
  if (error.status === 429 || error.code === "CHAT_QUOTA_EXCEEDED") {
    return {
      message: "The service is busy. Please try again in a minute.",
      retryable: true,
    };
  }
  if (error.code === "CHAT_SEARCH_UNAVAILABLE") {
    return {
      message: "Document search is temporarily unavailable. Please try again.",
      retryable: true,
    };
  }
  if (
    error.code === "CHAT_UNAVAILABLE" ||
    error.code === "CHAT_MODEL_NOT_FOUND" ||
    error.status === 503
  ) {
    return {
      message: "Chat is temporarily unavailable. Please try again.",
      retryable: true,
    };
  }
  if (error.code === "REQUEST_TIMEOUT") {
    return {
      message: "That took longer than expected. Please try again.",
      retryable: true,
    };
  }
  if (error.code === "NETWORK_ERROR") {
    return {
      message: "Could not connect to the service. Check your connection and try again.",
      retryable: true,
    };
  }
  return { message: error.message, retryable: false };
}

function AnswerText({
  answer,
  turnIndex,
  citations,
  citationRefs,
}: {
  answer: string;
  turnIndex: number;
  citations: Citation[];
  citationRefs: React.MutableRefObject<Map<string, HTMLElement>>;
}) {
  const citationsByNumber = new Map(citations.map((citation) => [citation.number, citation]));
  const markerPattern = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
  const pieces: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = markerPattern.exec(answer)) !== null) {
    if (match.index > lastIndex) {
      pieces.push(answer.slice(lastIndex, match.index));
    }

    pieces.push("[");
    const numberPattern = /\d+/g;
    let numberMatch: RegExpExecArray | null;
    let markerLastIndex = 0;
    while ((numberMatch = numberPattern.exec(match[1])) !== null) {
      if (numberMatch.index > markerLastIndex) {
        pieces.push(match[1].slice(markerLastIndex, numberMatch.index));
      }
      const number = Number(numberMatch[0]);
      const citation = citationsByNumber.get(number);
      if (citation) {
        pieces.push(
          <button
            aria-label={`Jump to citation ${number}, ${citation.filename}, page ${citation.page_number}`}
            className="citation-link font-semibold underline underline-offset-2"
            key={`marker-${turnIndex}-${key++}`}
            onClick={() => {
              const target = citationRefs.current.get(citationId(turnIndex, number));
              target?.scrollIntoView({ behavior: "smooth", block: "center" });
              target?.focus({ preventScroll: true });
            }}
            type="button"
          >
            {number}
          </button>,
        );
      } else {
        pieces.push(numberMatch[0]);
      }
      markerLastIndex = numberPattern.lastIndex;
    }
    if (markerLastIndex < match[1].length) {
      pieces.push(match[1].slice(markerLastIndex));
    }
    pieces.push("]");
    lastIndex = markerPattern.lastIndex;
  }

  if (lastIndex < answer.length) pieces.push(answer.slice(lastIndex));
  return <p className="answer-text whitespace-pre-wrap leading-7">{pieces}</p>;
}

export function ChatInterface() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [questionError, setQuestionError] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [activeTurnIndex, setActiveTurnIndex] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const requestController = useRef<AbortController | null>(null);
  const cancelledTurnIndex = useRef<number | null>(null);
  const citationRefs = useRef<Map<string, HTMLElement>>(new Map());
  const latestTurnRef = useRef<HTMLLIElement | null>(null);
  const readyDocuments = documents.filter((document) => document.status === "ready");
  const isLoading = activeTurnIndex !== null;

  const refreshDocuments = useCallback(async () => {
    setDocumentsLoading(true);
    setDocumentsError("");
    try {
      const result = await apiRequest<DocumentItem[]>("/documents");
      const ready = result.filter((document) => document.status === "ready");
      const validIds = new Set(ready.map((document) => document.id));
      setDocuments(ready);
      setSelectedIds((current) => current.filter((id) => validIds.has(id)));
    } catch (error) {
      setDocumentsError(
        error instanceof ApiError
          ? error.message
          : "Could not load your documents. Please try again.",
      );
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void refreshDocuments(), 0);
    return () => window.clearTimeout(timer);
  }, [refreshDocuments]);

  useEffect(() => {
    latestTurnRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [turns]);

  const sendQuestion = useCallback(
    async (turnIndex: number, questionText: string, requestedDocumentIds: string[]) => {
      const validIds = new Set(
        documents
          .filter((document) => document.status === "ready")
          .map((document) => document.id),
      );
      const documentIds = requestedDocumentIds.filter((id) => validIds.has(id));
      const controller = new AbortController();
      requestController.current = controller;
      cancelledTurnIndex.current = null;
      setActiveTurnIndex(turnIndex);
      setAnnouncement("");
      setTurns((current) =>
        current.map((turn) =>
          turn.index === turnIndex
            ? {
                ...turn,
                documentIds,
                response: undefined,
                error: undefined,
                retryable: false,
                isLoading: true,
              }
            : turn,
        ),
      );

      try {
        const response = await apiRequest<ChatResponse>("/chat", {
          method: "POST",
          body: {
            question: questionText,
            ...(documentIds.length > 0 ? { document_ids: documentIds } : {}),
          },
          timeoutMs: CHAT_REQUEST_TIMEOUT_MS,
          signal: controller.signal,
        });
        setTurns((current) =>
          current.map((turn) =>
            turn.index === turnIndex
              ? { ...turn, response, error: undefined, isLoading: false }
              : turn,
          ),
        );
        setAnnouncement("A cited answer is ready.");
      } catch (error) {
        if (cancelledTurnIndex.current === turnIndex) {
          setTurns((current) =>
            current.map((turn) =>
              turn.index === turnIndex
                ? { ...turn, error: undefined, retryable: false, isLoading: false }
                : turn,
            ),
          );
          setAnnouncement("The response was cancelled. The server may continue processing it.");
        } else if (error instanceof ApiError && error.code === "REQUEST_TIMEOUT") {
          setTurns((current) =>
            current.map((turn) =>
              turn.index === turnIndex
                ? {
                    ...turn,
                    error: "That took longer than expected. Please try again.",
                    retryable: true,
                    isLoading: false,
                  }
                : turn,
            ),
          );
        } else {
          const failure = friendlyChatError(error);
          setTurns((current) =>
            current.map((turn) =>
              turn.index === turnIndex
                ? {
                    ...turn,
                    error: failure.message,
                    retryable: failure.retryable,
                    isLoading: false,
                  }
                : turn,
            ),
          );
          setAnnouncement(failure.message);
        }
      } finally {
        if (requestController.current === controller) {
          requestController.current = null;
        }
        setActiveTurnIndex((current) => (current === turnIndex ? null : current));
      }
    },
    [documents],
  );

  function submitQuestion() {
    const normalized = question.trim();
    if (isLoading) return;
    if (!normalized) {
      setQuestionError("Enter a question.");
      return;
    }
    if (normalized.length > CHAT_MAX_QUESTION_CHARS) {
      setQuestionError(`Questions must be ${CHAT_MAX_QUESTION_CHARS} characters or shorter.`);
      return;
    }

    setQuestionError("");
    setQuestion("");
    const turnIndex = turns.length;
    const validIds = new Set(readyDocuments.map((document) => document.id));
    const documentIds = selectedIds.filter((id) => validIds.has(id));
    setTurns((current) => [
      ...current,
      {
        index: turnIndex,
        question: normalized,
        documentIds,
        isLoading: true,
      },
    ]);
    void sendQuestion(turnIndex, normalized, documentIds);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      event.keyCode !== 229
    ) {
      event.preventDefault();
      submitQuestion();
    }
  }

  function toggleDocument(documentId: string) {
    setSelectedIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId],
    );
  }

  function cancelRequest() {
    if (activeTurnIndex !== null) cancelledTurnIndex.current = activeTurnIndex;
    requestController.current?.abort();
  }

  return (
    <main className="workspace-page chat-page" id="main-content">
      <header className="workspace-page-header">
        <p className="eyebrow">
          Ask your documents
        </p>
        <h1 className="page-title mt-2 text-3xl font-bold tracking-tight">
          Cited chat
        </h1>
        <p className="page-description mt-3">
          Answers are grounded in the documents you choose and include source citations.
        </p>
        <p className="helper-text mt-2 text-sm">
          Each question is answered independently.
        </p>
      </header>

      <section
        aria-labelledby="document-filter-heading"
        className="glass-panel chat-filter-panel"
      >
        <div className="chat-filter-heading">
          <div>
            <p className="eyebrow">Search scope</p>
            <h2 id="document-filter-heading" className="section-subheading font-semibold">
              Choose documents
            </h2>
          </div>
          {readyDocuments.length > 0 && (
            <span className="helper-text chat-selected-count" aria-live="polite">
              {selectedIds.length === 0
                ? "All ready documents"
                : `${selectedIds.length} selected`}
            </span>
          )}
        </div>
        {documentsLoading && (
          <ColdStartStatus className="helper-text mt-3 text-sm">
            Loading ready documents…
          </ColdStartStatus>
        )}
        {documentsError && (
          <div className="mt-3" role="alert">
            <p className="notice notice-error text-sm">
              <NoticeIcon kind="error" />
              {documentsError}
            </p>
            <button
              className="citation-link mt-2 text-sm font-semibold underline"
              onClick={() => void refreshDocuments()}
              type="button"
            >
              Try loading documents again
            </button>
          </div>
        )}
        {!documentsLoading && !documentsError && readyDocuments.length === 0 && (
          <div className="page-description mt-3 text-sm">
            <p>You do not have any ready documents to search yet.</p>
            <Link
              className="citation-link mt-2 inline-block font-semibold underline underline-offset-2"
              href="/documents"
            >
              Go to Documents
            </Link>
          </div>
        )}
        {!documentsLoading && readyDocuments.length > 0 && (
          <>
            <div className="chat-filter-description">
              <p className="helper-text text-sm">
                Select specific sources, or leave all unchecked to search every ready document.
              </p>
              <button
                className="citation-link text-sm font-semibold underline underline-offset-2"
                disabled={documentsLoading}
                onClick={() => void refreshDocuments()}
                type="button"
              >
                Refresh ready documents
              </button>
            </div>
            <ul aria-label="Ready documents" className="document-chip-list">
              {readyDocuments.map((document) => (
                <li key={document.id}>
                  <label className="document-choice document-chip">
                    <input
                      checked={selectedIds.includes(document.id)}
                      className="document-checkbox"
                      onChange={() => toggleDocument(document.id)}
                      type="checkbox"
                    />
                    <span className="document-filename" title={document.filename}>
                      {document.filename}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-label="Conversation" className="chat-conversation">
        {turns.length === 0 && (
          <div className="glass-panel empty-state chat-empty-state">
            <span aria-hidden="true" className="chat-empty-mark">?</span>
            <div>
              <p className="eyebrow">Grounded answers</p>
              <h2 className="section-subheading font-semibold">Ask your first question</h2>
              <p className="page-description">
                Choose documents above if you want to limit the search. Answers include links to their source passages.
              </p>
            </div>
          </div>
        )}
        <ol className="chat-turn-list">
          {turns.map((turn, index) => {
            const isLatest = index === turns.length - 1;
            const response = turn.response;
            const notFound = response ? isNotFound(response) : false;
            return (
              <li
                className="chat-turn scroll-mt-6"
                key={turn.index}
                ref={isLatest ? latestTurnRef : undefined}
              >
                <div className="user-message">
                  <p className="user-message-label text-xs font-semibold uppercase tracking-wide">
                    You asked
                  </p>
                  <p className="mt-2 whitespace-pre-wrap leading-7">{turn.question}</p>
                </div>

                {turn.isLoading && (
                  <div className="notice notice-info chat-thinking" role="status">
                    <NoticeIcon kind="info" />
                    <div className="min-w-0">
                      <p className="font-semibold">Thinking…</p>
                      <p className="helper-text mt-1 text-sm">
                        Searching your documents and preparing a cited answer.
                      </p>
                      <button
                        className="button-secondary mt-3 rounded-lg px-3 py-2 text-sm"
                        onClick={cancelRequest}
                        type="button"
                      >
                        Cancel response
                      </button>
                    </div>
                  </div>
                )}

                {turn.error && (
                  <div className="notice notice-error chat-error" role="alert">
                    <NoticeIcon kind="error" />
                    <div className="min-w-0">
                      <p className="text-sm">{turn.error}</p>
                      {turn.retryable && (
                        <button
                          className="button-secondary mt-3 rounded-lg px-3 py-2 text-sm"
                          disabled={isLoading}
                          onClick={() =>
                            void sendQuestion(turn.index, turn.question, turn.documentIds)
                          }
                          type="button"
                        >
                          Retry this question
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {response && (
                  <div
                    className={`assistant-message ${
                      notFound
                        ? "notice notice-warning not-found-message"
                        : "glass-panel answer-card"
                    }`}
                  >
                    {notFound ? (
                      <>
                        <NoticeIcon kind="warning" />
                        <div className="min-w-0">
                          <h2 className="font-semibold">No matching information found</h2>
                          <p className="mt-2">{response.answer}</p>
                          <p className="helper-text mt-2 text-sm">
                            Try rephrasing your question or upload more relevant documents.
                          </p>
                        </div>
                      </>
                    ) : (
                      <>
                        <h2 className="section-subheading font-semibold">Answer</h2>
                        <div className="mt-3">
                          <AnswerText
                            answer={response.answer}
                            citationRefs={citationRefs}
                            citations={response.citations}
                            turnIndex={turn.index}
                          />
                        </div>
                        {response.citations.length > 0 && (
                          <section
                            aria-label="Sources"
                            className="sources-section mt-5 border-t pt-4"
                          >
                            <h3 className="section-subheading font-semibold">Sources</h3>
                            <ol className="mt-3 space-y-3">
                              {response.citations.map((citation) => {
                                const id = citationId(turn.index, citation.number);
                                return (
                                  <li
                                    aria-label={`Citation ${citation.number}: ${citation.filename}, page ${citation.page_number}`}
                                    className="citation-card scroll-mt-6 rounded-xl p-4"
                                    id={id}
                                    key={id}
                                    ref={(element) => {
                                      if (element) citationRefs.current.set(id, element);
                                      else citationRefs.current.delete(id);
                                    }}
                                    tabIndex={-1}
                                  >
                                    <p className="document-filename font-semibold">
                                      [{citation.number}] {citation.filename} — page{" "}
                                      {citation.page_number}
                                    </p>
                                    <p className="page-description mt-2 whitespace-pre-wrap text-sm leading-6">
                                      {citation.snippet}
                                    </p>
                                  </li>
                                );
                              })}
                            </ol>
                          </section>
                        )}
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>

      <section className="chat-composer chat-composer-panel">
        <label className="field-label block text-sm font-semibold" htmlFor="chat-question">
          Your question
        </label>
        <textarea
          aria-describedby={questionError ? "chat-question-error chat-question-count" : "chat-question-count"}
          aria-invalid={Boolean(questionError)}
          className="input-shell mt-2 min-h-24 w-full resize-y px-4 py-3"
          disabled={isLoading}
          id="chat-question"
          maxLength={CHAT_MAX_QUESTION_CHARS}
          onChange={(event) => {
            setQuestion(event.target.value);
            if (questionError) setQuestionError("");
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents…"
          value={question}
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <p
            className="helper-text text-xs"
            id="chat-question-count"
            aria-live="polite"
          >
            {question.length}/{CHAT_MAX_QUESTION_CHARS} characters · Enter to send, Shift+Enter for a new line
          </p>
          <div className="flex items-center gap-3">
            {questionError && (
              <p className="notice notice-error text-sm" id="chat-question-error" role="alert">
                <NoticeIcon kind="error" />
                {questionError}
              </p>
            )}
            <button
              className="button-primary rounded-lg px-5 py-3 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading || documentsLoading || readyDocuments.length === 0}
              onClick={submitQuestion}
              type="button"
            >
              {isLoading ? "Thinking…" : "Ask"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
