"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type { DocumentItem, DocumentUploadResponse } from "@/lib/types";

const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024; // Mirrors the backend default in app/core/config.py.
const DOCUMENT_UPLOAD_TIMEOUT_MS = 120_000;

type Notice = { kind: "success" | "error" | "progress"; message: string };

function documentStatus(status: string): string {
  switch (status) {
    case "processing":
      return "Processing";
    case "ready":
      return "Ready";
    case "failed":
      return "Failed";
    case "embedding_failed":
      return "Embedding failed";
    default:
      return status.replaceAll("_", " ");
  }
}

function formattedDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function getErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Something went wrong. Please try again.";
}

export function DocumentsManager() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [highlightedDocumentId, setHighlightedDocumentId] = useState<string | null>(
    null,
  );
  const [deleteTarget, setDeleteTarget] = useState<DocumentItem | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(() => new Set());
  const [retryingIds, setRetryingIds] = useState<Set<string>>(() => new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deleteDialogRef = useRef<HTMLDialogElement>(null);

  const refreshDocuments = useCallback(async () => {
    setIsLoading(true);
    setListError("");
    try {
      const result = await apiRequest<DocumentItem[]>("/documents");
      setDocuments(result);
    } catch (error) {
      setListError(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void refreshDocuments(), 0);
    return () => window.clearTimeout(timer);
  }, [refreshDocuments]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setNotice(null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || isUploading) return;

    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setNotice({ kind: "error", message: "Choose a PDF file with a .pdf extension." });
      return;
    }
    if (selectedFile.size > MAX_UPLOAD_SIZE_BYTES) {
      setNotice({ kind: "error", message: "The PDF must be 10 MiB or smaller." });
      return;
    }
    if (selectedFile.type && selectedFile.type !== "application/pdf") {
      setNotice({ kind: "error", message: "Choose a PDF file." });
      return;
    }

    setIsUploading(true);
    setNotice({
      kind: "progress",
      message: "Uploading and processing your PDF. This can take a minute; please keep this page open.",
    });
    try {
      const signature = await selectedFile.slice(0, 5).text();
      if (!signature.startsWith("%PDF-")) {
        setNotice({ kind: "error", message: "This file does not appear to be a valid PDF." });
        return;
      }

      const formData = new FormData();
      formData.append("file", selectedFile);
      const uploaded = await apiRequest<DocumentUploadResponse>("/documents", {
        method: "POST",
        body: formData,
        timeoutMs: DOCUMENT_UPLOAD_TIMEOUT_MS,
      });
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";

      if (uploaded.duplicate) {
        setHighlightedDocumentId(uploaded.id);
        setNotice({
          kind: "success",
          message:
            uploaded.status === "failed"
              ? "This PDF was already uploaded, but its previous processing attempt failed. Re-uploading did not restart it."
              : "This PDF was already uploaded. Its existing document is highlighted below.",
        });
      } else {
        setNotice({
          kind: "success",
          message: `Upload complete. Current status: ${documentStatus(uploaded.status)}.`,
        });
      }
      await refreshDocuments();
    } catch (error) {
      setNotice({ kind: "error", message: getErrorMessage(error) });
    } finally {
      setIsUploading(false);
    }
  }

  function openDeleteDialog(document: DocumentItem) {
    setDeleteTarget(document);
  }

  function closeDeleteDialog() {
    if (deleteTarget && deletingIds.has(deleteTarget.id)) return;
    deleteDialogRef.current?.close();
    setDeleteTarget(null);
  }

  function updateBusyIds(
    setter: (update: (current: Set<string>) => Set<string>) => void,
    documentId: string,
    isBusy: boolean,
  ) {
    setter((current) => {
      const next = new Set(current);
      if (isBusy) next.add(documentId);
      else next.delete(documentId);
      return next;
    });
  }

  async function confirmDelete() {
    if (!deleteTarget || deletingIds.has(deleteTarget.id)) return;
    const target = deleteTarget;
    updateBusyIds(setDeletingIds, target.id, true);
    setNotice({ kind: "progress", message: `Deleting ${target.filename}…` });
    try {
      await apiRequest<void>(`/documents/${target.id}`, { method: "DELETE" });
      setNotice({ kind: "success", message: "Document deleted." });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNotice({
          kind: "success",
          message: "That document was already gone. The list has been refreshed.",
        });
      } else {
        setNotice({ kind: "error", message: getErrorMessage(error) });
      }
    } finally {
      deleteDialogRef.current?.close();
      setDeleteTarget(null);
      updateBusyIds(setDeletingIds, target.id, false);
      await refreshDocuments();
    }
  }

  async function retryEmbedding(document: DocumentItem) {
    if (retryingIds.has(document.id)) return;
    updateBusyIds(setRetryingIds, document.id, true);
    setNotice({ kind: "progress", message: `Retrying embedding for ${document.filename}…` });
    try {
      const updated = await apiRequest<DocumentItem>(
        `/documents/${document.id}/retry-embedding`,
        { method: "POST" },
      );
      setNotice({
        kind: "success",
        message: `Embedding retry finished. Current status: ${documentStatus(updated.status)}.`,
      });
      await refreshDocuments();
    } catch (error) {
      setNotice({ kind: "error", message: getErrorMessage(error) });
    } finally {
      updateBusyIds(setRetryingIds, document.id, false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-800">
          Your workspace
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
          Documents
        </h1>
        <p className="mt-3 max-w-2xl text-slate-600">
          Upload PDFs to search and ask questions about them. Uploading includes
          text extraction and embedding, so larger files may take a little while.
        </p>
      </header>

      <section
        aria-labelledby="upload-heading"
        className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
      >
        <h2 id="upload-heading" className="text-lg font-semibold text-slate-950">
          Add a PDF
        </h2>
        <form className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end" onSubmit={handleUpload}>
          <div className="min-w-0 flex-1">
            <label
              className="block text-sm font-medium text-slate-800"
              htmlFor="document-file"
            >
              Choose a PDF
            </label>
            <input
              ref={fileInputRef}
              accept="application/pdf,.pdf"
              className="mt-2 block w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-800 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:font-semibold file:text-slate-800"
              disabled={isUploading}
              id="document-file"
              onChange={handleFileChange}
              type="file"
            />
            <p className="mt-2 text-xs text-slate-500">
              PDF only, up to 10 MiB.
            </p>
          </div>
          <button
            className="rounded-lg bg-slate-950 px-5 py-3 font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!selectedFile || isUploading}
            type="submit"
          >
            {isUploading ? "Uploading…" : "Upload PDF"}
          </button>
        </form>
        {isUploading && (
          <p className="mt-4 text-sm text-cyan-900">
            Processing your PDF. This can take a minute; please keep this page open.
          </p>
        )}
      </section>

      <section aria-labelledby="list-heading" className="mt-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="list-heading" className="text-xl font-semibold text-slate-950">
            Your files
          </h2>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-white disabled:opacity-60"
            disabled={isLoading}
            onClick={() => void refreshDocuments()}
            type="button"
          >
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {notice && (
          <p
            aria-live={notice.kind === "error" ? "assertive" : "polite"}
            className={`mt-4 rounded-lg p-3 text-sm ${
              notice.kind === "error"
                ? "bg-rose-50 text-rose-800"
                : notice.kind === "success"
                  ? "bg-emerald-50 text-emerald-900"
                  : "bg-cyan-50 text-cyan-900"
            }`}
            role={notice.kind === "error" ? "alert" : "status"}
          >
            {notice.message}
          </p>
        )}

        {isLoading && documents.length === 0 && (
          <p className="mt-5 text-slate-600" role="status">
            Loading your documents…
          </p>
        )}
        {listError && (
          <p className="mt-5 rounded-lg bg-rose-50 p-4 text-sm text-rose-800" role="alert">
            {listError}
          </p>
        )}
        {!isLoading && !listError && documents.length === 0 && (
          <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <h3 className="font-semibold text-slate-900">No documents yet</h3>
            <p className="mt-2 text-sm text-slate-600">
              Choose a PDF above to add your first document.
            </p>
          </div>
        )}
        {documents.length > 0 && (
          <ul className="mt-5 space-y-3">
            {documents.map((document) => {
              const isDeleting = deletingIds.has(document.id);
              const isRetrying = retryingIds.has(document.id);
              const isHighlighted = highlightedDocumentId === document.id;
              return (
                <li
                  className={`rounded-xl border bg-white p-4 shadow-sm sm:p-5 ${
                    isHighlighted
                      ? "border-cyan-700 ring-2 ring-cyan-200"
                      : "border-slate-200"
                  }`}
                  data-highlighted={isHighlighted ? "true" : undefined}
                  data-testid={`document-${document.id}`}
                  key={document.id}
                >
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <h3
                        className="max-w-full truncate font-semibold text-slate-950 sm:max-w-xl"
                        title={document.filename}
                      >
                        {document.filename}
                      </h3>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className="inline-flex rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-800">
                          {documentStatus(document.status)}
                        </span>
                        <span className="text-sm text-slate-600">
                          {document.page_count}{" "}
                          {document.page_count === 1 ? "page" : "pages"}
                        </span>
                        <span className="text-sm text-slate-600">
                          Added {formattedDate(document.created_at)}
                        </span>
                      </div>
                      {document.failure_reason && (
                        <p className="mt-3 text-sm text-rose-800">
                          Failure reason: {document.failure_reason}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 sm:justify-end">
                      {document.status === "embedding_failed" && (
                        <button
                          aria-label={`Retry embedding for ${document.filename}`}
                          className="rounded-lg border border-cyan-800 px-3 py-2 text-sm font-semibold text-cyan-900 hover:bg-cyan-50 disabled:opacity-60"
                          disabled={isRetrying || isDeleting}
                          onClick={() => void retryEmbedding(document)}
                          type="button"
                        >
                          {isRetrying ? "Retrying…" : "Retry embedding"}
                        </button>
                      )}
                      <button
                        aria-label={`Delete ${document.filename}`}
                        className="rounded-lg border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-50 disabled:opacity-60"
                        disabled={isDeleting || isRetrying}
                        onClick={() => openDeleteDialog(document)}
                        type="button"
                      >
                        {isDeleting ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {deleteTarget && (
        <dialog
          aria-labelledby="delete-dialog-title"
          aria-modal="true"
          className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-slate-200 bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-950/40"
          onCancel={(event) => {
            event.preventDefault();
            closeDeleteDialog();
          }}
          ref={(element) => {
            deleteDialogRef.current = element;
            if (element && !element.open) element.showModal();
          }}
        >
          <div className="p-6">
            <h2 id="delete-dialog-title" className="text-lg font-semibold">
              Delete document?
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Delete <span className="font-semibold text-slate-900">{deleteTarget.filename}</span>?
              This cannot be undone.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-60"
                disabled={deletingIds.has(deleteTarget.id)}
                onClick={closeDeleteDialog}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-lg bg-rose-700 px-4 py-2 font-semibold text-white hover:bg-rose-800 disabled:opacity-60"
                disabled={deletingIds.has(deleteTarget.id)}
                onClick={() => void confirmDelete()}
                type="button"
              >
                {deletingIds.has(deleteTarget.id) ? "Deleting…" : "Delete document"}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </main>
  );
}
