"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
} from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type { DocumentItem, DocumentUploadResponse } from "@/lib/types";
import { ColdStartStatus } from "./cold-start-status";

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

function statusKind(status: string): "info" | "success" | "error" | "warning" {
  switch (status) {
    case "ready":
      return "success";
    case "failed":
      return "error";
    case "embedding_failed":
      return "warning";
    default:
      return "info";
  }
}

function StatusIcon({ kind }: { kind: "info" | "success" | "error" | "warning" }) {
  const paths = {
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8h.01" /></>,
    success: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    error: <><circle cx="12" cy="12" r="9" /><path d="m9 9 6 6m0-6-6 6" /></>,
    warning: <><path d="m12 3 10 18H2L12 3Z" /><path d="M12 9v4m0 3h.01" /></>,
  };
  return (
    <svg aria-hidden="true" className="status-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      {paths[kind]}
    </svg>
  );
}

function NoticeIcon({ kind }: { kind: Notice["kind"] }) {
  if (kind === "progress") {
    return (
      <svg aria-hidden="true" className="notice-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
    );
  }
  return <StatusIcon kind={kind} />;
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
  const [isDragActive, setIsDragActive] = useState(false);
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

  function handleFileDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(false);
    if (isUploading) return;
    setSelectedFile(event.dataTransfer.files[0] ?? null);
    if (fileInputRef.current) fileInputRef.current.value = "";
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
    <main className="workspace-page documents-page" id="main-content">
      <header className="workspace-page-header">
        <p className="eyebrow">
          Your workspace
        </p>
        <h1 className="page-title mt-2 text-3xl font-bold tracking-tight">
          Documents
        </h1>
        <p className="page-description mt-3 max-w-2xl">
          Upload PDFs to search and ask questions about them. Uploading includes
          text extraction and embedding, so larger files may take a little while.
        </p>
        <p className="helper-text mt-2 max-w-2xl text-xs">
          We do not keep your original PDF file. We store extracted text passages and numeric embeddings so we can search them, until you delete the document. Text from your documents is sent to the Google Gemini API to create embeddings and answers. Do not upload sensitive, confidential or personal documents.
        </p>
      </header>

      <section
        aria-labelledby="upload-heading"
        className="glass-panel mt-8 p-5 sm:p-7"
      >
        <h2 id="upload-heading" className="section-subheading text-lg font-semibold">
          Add a PDF
        </h2>
        <form className="upload-form" onSubmit={handleUpload}>
          <div
            className={`upload-dropzone${isDragActive ? " upload-dropzone-active" : ""}`}
            data-drag-active={isDragActive}
            onDragEnter={(event) => {
              event.preventDefault();
              if (!isUploading) setIsDragActive(true);
            }}
            onDragLeave={(event) => {
              if (
                event.relatedTarget instanceof Node &&
                !event.currentTarget.contains(event.relatedTarget)
              ) {
                setIsDragActive(false);
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              if (!isUploading) setIsDragActive(true);
            }}
            onDrop={handleFileDrop}
          >
            <label
              className="field-label upload-file-label"
              htmlFor="document-file"
            >
              Choose a PDF
            </label>
            <input
              ref={fileInputRef}
              accept="application/pdf,.pdf"
              aria-describedby="upload-help"
              className="file-input"
              disabled={isUploading}
              id="document-file"
              onChange={handleFileChange}
              type="file"
            />
            <p className="helper-text" id="upload-help">
              Drag a PDF here, or use the file picker. PDF only, up to 10 MiB.
            </p>
            {selectedFile && (
              <p aria-live="polite" className="upload-selected-file">
                Selected: {selectedFile.name}
              </p>
            )}
          </div>
          <button
            className="button-primary upload-submit"
            disabled={!selectedFile || isUploading}
            type="submit"
          >
            {isUploading ? "Uploading…" : "Upload PDF"}
          </button>
        </form>
        {isUploading && (
          <p className="notice notice-info mt-4 text-sm" role="status">
            <StatusIcon kind="info" />
            Processing your PDF. This can take a minute; please keep this page open.
          </p>
        )}
      </section>

      <section aria-labelledby="list-heading" className="documents-list-section">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="list-heading" className="section-subheading text-xl font-semibold">
            Your files
          </h2>
          <button
            className="button-secondary rounded-lg px-3 py-2 text-sm disabled:opacity-60"
            disabled={isLoading}
            onClick={() => void refreshDocuments()}
            type="button"
          >
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {notice && (
          <div
            aria-live={notice.kind === "error" ? "assertive" : "polite"}
            className={`notice notice-${notice.kind === "progress" ? "info" : notice.kind} mt-4 text-sm`}
            role={notice.kind === "error" ? "alert" : "status"}
          >
            <NoticeIcon kind={notice.kind} />
            {notice.message}
          </div>
        )}

        {isLoading && documents.length === 0 && (
          <ColdStartStatus className="helper-text mt-5">
            Loading your documents…
          </ColdStartStatus>
        )}
        {listError && (
          <p className="notice notice-error mt-5 text-sm" role="alert">
            <StatusIcon kind="error" />
            {listError}
          </p>
        )}
        {!isLoading && !listError && documents.length === 0 && (
          <div className="glass-panel empty-state mt-5 p-8 text-center">
            <h3 className="section-subheading font-semibold">No documents yet</h3>
            <p className="page-description mt-2 text-sm">
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
                  className={`document-card glass-panel p-4 sm:p-5 ${
                    isHighlighted
                      ? "document-card-highlight"
                      : ""
                  }`}
                  data-highlighted={isHighlighted ? "true" : undefined}
                  data-testid={`document-${document.id}`}
                  key={document.id}
                >
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <h3
                        className="document-filename max-w-full truncate font-semibold sm:max-w-xl"
                        title={document.filename}
                      >
                        {document.filename}
                      </h3>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className={`status-badge status-${statusKind(document.status)}`}>
                          <StatusIcon kind={statusKind(document.status)} />
                          {documentStatus(document.status)}
                        </span>
                        <span className="helper-text text-sm">
                          {document.page_count}{" "}
                          {document.page_count === 1 ? "page" : "pages"}
                        </span>
                        <span className="helper-text text-sm">
                          Added {formattedDate(document.created_at)}
                        </span>
                      </div>
                      {document.failure_reason && (
                        <p className="notice notice-error mt-3 text-sm">
                          <StatusIcon kind="error" />
                          Failure reason: {document.failure_reason}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 sm:justify-end">
                      {document.status === "embedding_failed" && (
                        <button
                          aria-label={`Retry embedding for ${document.filename}`}
                          className="button-secondary rounded-lg px-3 py-2 text-sm disabled:opacity-60"
                          disabled={isRetrying || isDeleting}
                          onClick={() => void retryEmbedding(document)}
                          type="button"
                        >
                          {isRetrying ? "Retrying…" : "Retry embedding"}
                        </button>
                      )}
                      <button
                        aria-label={`Delete ${document.filename}`}
                        className="button-danger rounded-lg px-3 py-2 text-sm disabled:opacity-60"
                        disabled={isDeleting || isRetrying}
                        onClick={() => openDeleteDialog(document)}
                        type="button"
                      >
                        <svg aria-hidden="true" className="status-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                          <path d="M4 7h16m-10 4v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" />
                        </svg>
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
          className="delete-dialog m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl p-0 shadow-xl"
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
            <p className="notice notice-warning mt-3 text-sm leading-6">
              <StatusIcon kind="warning" />
              <span>
                Delete <span className="document-filename font-semibold">{deleteTarget.filename}</span>?
                This cannot be undone.
              </span>
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="button-secondary rounded-lg px-4 py-2 disabled:opacity-60"
                disabled={deletingIds.has(deleteTarget.id)}
                onClick={closeDeleteDialog}
                type="button"
              >
                Cancel
              </button>
              <button
                className="button-danger rounded-lg px-4 py-2 disabled:opacity-60"
                disabled={deletingIds.has(deleteTarget.id)}
                onClick={() => void confirmDelete()}
                type="button"
              >
                <svg aria-hidden="true" className="status-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                  <path d="M4 7h16m-10 4v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" />
                </svg>
                {deletingIds.has(deleteTarget.id) ? "Deleting…" : "Delete document"}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </main>
  );
}
