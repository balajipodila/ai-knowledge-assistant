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
            className="font-semibold text-cyan-800 underline underline-offset-2"
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
  return <p className="whitespace-pre-wrap leading-7 text-slate-800">{pieces}</p>;
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
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-800">
          Ask your documents
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
          Cited chat
        </h1>
        <p className="mt-3 text-slate-600">
          Answers are grounded in the documents you choose and include source citations.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Each question is answered independently.
        </p>
      </header>

      <section
        aria-labelledby="document-filter-heading"
        className="mt-7 rounded-2xl border border-slate-200 bg-white p-5"
      >
        <h2 id="document-filter-heading" className="font-semibold text-slate-950">
          Search in documents
        </h2>
        {documentsLoading && (
          <p className="mt-3 text-sm text-slate-600" role="status">
            Loading ready documents…
          </p>
        )}
        {documentsError && (
          <div className="mt-3" role="alert">
            <p className="text-sm text-rose-800">{documentsError}</p>
            <button
              className="mt-2 text-sm font-semibold text-cyan-800 underline"
              onClick={() => void refreshDocuments()}
              type="button"
            >
              Try loading documents again
            </button>
          </div>
        )}
        {!documentsLoading && !documentsError && readyDocuments.length === 0 && (
          <div className="mt-3 text-sm text-slate-700">
            <p>You do not have any ready documents to search yet.</p>
            <Link
              className="mt-2 inline-block font-semibold text-cyan-800 underline underline-offset-2"
              href="/documents"
            >
              Go to Documents
            </Link>
          </div>
        )}
        {!documentsLoading && readyDocuments.length > 0 && (
          <>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-600">
                Leave all unchecked to search every ready document.
              </p>
              <button
                className="text-sm font-semibold text-cyan-800 underline underline-offset-2"
                disabled={documentsLoading}
                onClick={() => void refreshDocuments()}
                type="button"
              >
                Refresh ready documents
              </button>
            </div>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {readyDocuments.map((document) => (
                <li key={document.id}>
                  <label className="flex min-w-0 cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                    <input
                      checked={selectedIds.includes(document.id)}
                      className="mt-1 h-4 w-4 accent-cyan-800"
                      onChange={() => toggleDocument(document.id)}
                      type="checkbox"
                    />
                    <span className="min-w-0 truncate text-sm font-medium text-slate-800" title={document.filename}>
                      {document.filename}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-label="Conversation" className="mt-7">
        {turns.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <h2 className="font-semibold text-slate-900">Ask your first question</h2>
            <p className="mt-2 text-sm text-slate-600">
              Choose documents above if you want to limit the search.
            </p>
          </div>
        )}
        <ol className="space-y-6">
          {turns.map((turn, index) => {
            const isLatest = index === turns.length - 1;
            const response = turn.response;
            const notFound = response ? isNotFound(response) : false;
            return (
              <li
                className="scroll-mt-6 space-y-4"
                key={turn.index}
                ref={isLatest ? latestTurnRef : undefined}
              >
                <div className="ml-auto max-w-3xl rounded-2xl bg-slate-900 p-4 text-white sm:p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                    You asked
                  </p>
                  <p className="mt-2 whitespace-pre-wrap leading-7">{turn.question}</p>
                </div>

                {turn.isLoading && (
                  <div className="rounded-2xl border border-cyan-200 bg-cyan-50 p-4" role="status">
                    <p className="font-semibold text-cyan-950">Thinking…</p>
                    <p className="mt-1 text-sm text-cyan-900">
                      Searching your documents and preparing a cited answer.
                    </p>
                    <button
                      className="mt-3 rounded-lg border border-cyan-800 px-3 py-2 text-sm font-semibold text-cyan-950 hover:bg-white"
                      onClick={cancelRequest}
                      type="button"
                    >
                      Cancel response
                    </button>
                  </div>
                )}

                {turn.error && (
                  <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4" role="alert">
                    <p className="text-sm text-rose-900">{turn.error}</p>
                    {turn.retryable && (
                      <button
                        className="mt-3 rounded-lg border border-rose-800 px-3 py-2 text-sm font-semibold text-rose-900 hover:bg-white"
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
                )}

                {response && (
                  <div
                    className={`rounded-2xl border p-4 sm:p-5 ${
                      notFound
                        ? "border-amber-300 bg-amber-50"
                        : "border-slate-200 bg-white"
                    }`}
                  >
                    {notFound ? (
                      <>
                        <h2 className="font-semibold text-amber-950">No matching information found</h2>
                        <p className="mt-2 text-slate-900">{response.answer}</p>
                        <p className="mt-2 text-sm text-amber-900">
                          Try rephrasing your question or upload more relevant documents.
                        </p>
                      </>
                    ) : (
                      <>
                        <h2 className="font-semibold text-slate-950">Answer</h2>
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
                            className="mt-5 border-t border-slate-200 pt-4"
                          >
                            <h3 className="font-semibold text-slate-900">Sources</h3>
                            <ol className="mt-3 space-y-3">
                              {response.citations.map((citation) => {
                                const id = citationId(turn.index, citation.number);
                                return (
                                  <li
                                    aria-label={`Citation ${citation.number}: ${citation.filename}, page ${citation.page_number}`}
                                    className="scroll-mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 focus:outline-2 focus:outline-offset-2 focus:outline-cyan-700"
                                    id={id}
                                    key={id}
                                    ref={(element) => {
                                      if (element) citationRefs.current.set(id, element);
                                      else citationRefs.current.delete(id);
                                    }}
                                    tabIndex={-1}
                                  >
                                    <p className="font-semibold text-slate-950">
                                      [{citation.number}] {citation.filename} — page{" "}
                                      {citation.page_number}
                                    </p>
                                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
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

      <section className="sticky bottom-0 mt-8 border-t border-slate-200 bg-slate-50/95 py-4 backdrop-blur">
        <label className="block text-sm font-semibold text-slate-800" htmlFor="chat-question">
          Your question
        </label>
        <textarea
          aria-describedby={questionError ? "chat-question-error chat-question-count" : "chat-question-count"}
          aria-invalid={Boolean(questionError)}
          className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-950"
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
            className="text-xs text-slate-600"
            id="chat-question-count"
            aria-live="polite"
          >
            {question.length}/{CHAT_MAX_QUESTION_CHARS} characters · Enter to send, Shift+Enter for a new line
          </p>
          <div className="flex items-center gap-3">
            {questionError && (
              <p className="text-sm text-rose-800" id="chat-question-error" role="alert">
                {questionError}
              </p>
            )}
            <button
              className="rounded-lg bg-slate-950 px-5 py-3 font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
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
