"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type { DocumentItem } from "@/lib/types";
import { ColdStartStatus } from "./cold-start-status";

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

function statusLabel(status: string): string {
  switch (status) {
    case "embedding_failed":
      return "Embedding failed";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

function formatUploadDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Could not load your documents. Please try again.";
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <article className="dashboard-metric glass-panel">
      <h2 className="helper-text">{label}</h2>
      <p className="dashboard-metric-value">{value}</p>
    </article>
  );
}

export function DashboardOverview() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const requestDocuments = useCallback(
    () => apiRequest<DocumentItem[]>("/documents"),
    [],
  );

  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const result = await requestDocuments();
      setDocuments(result);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [requestDocuments]);

  useEffect(() => {
    let active = true;
    requestDocuments()
      .then((result) => {
        if (active) setDocuments(result);
      })
      .catch((loadError: unknown) => {
        if (active) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [requestDocuments]);

  const failedCount = documents.filter(
    ({ status }) => status === "failed" || status === "embedding_failed",
  ).length;
  const totalPages = documents.reduce(
    (total, document) => total + Math.max(0, document.page_count || 0),
    0,
  );
  const latestDocuments = [...documents]
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
    .slice(0, 5);

  return (
    <main className="workspace-page dashboard-page" id="main-content">
      <header className="workspace-page-header">
        <p className="eyebrow">Your workspace</p>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-description">
          A quick view of the PDFs in your account.
        </p>
      </header>

      <nav aria-label="Quick actions" className="dashboard-actions">
        <Link className="button-primary" href="/documents">
          Upload a PDF
        </Link>
        <Link className="button-secondary" href="/chat">
          Ask a question
        </Link>
      </nav>

      {isLoading && documents.length === 0 && (
        <ColdStartStatus className="helper-text dashboard-loading">
          Loading your dashboard…
        </ColdStartStatus>
      )}
      {error && (
        <div className="notice notice-error dashboard-error" role="alert">
          <span>{error}</span>
          <button className="button-secondary" onClick={() => void loadDocuments()} type="button">
            Try again
          </button>
        </div>
      )}
      {!isLoading && !error && documents.length === 0 && (
        <section aria-labelledby="dashboard-empty-title" className="glass-panel dashboard-empty">
          <p className="eyebrow">A fresh start</p>
          <h2 className="section-subheading" id="dashboard-empty-title">
            No documents yet
          </h2>
          <p className="page-description">
            Upload a PDF to see its processing status and ask questions about its content.
          </p>
          <Link className="button-primary" href="/documents">
            Upload your first PDF
          </Link>
        </section>
      )}
      {!error && documents.length > 0 && (
        <>
          <section aria-label="Document overview" className="dashboard-metrics">
            <MetricCard label="Total documents" value={documents.length} />
            <MetricCard
              label="Ready"
              value={documents.filter(({ status }) => status === "ready").length}
            />
            <MetricCard label="Failed or embedding failed" value={failedCount} />
            <MetricCard label="Total pages" value={totalPages} />
          </section>

          <section aria-labelledby="latest-uploads-title" className="dashboard-latest">
            <div className="dashboard-section-heading">
              <div>
                <p className="eyebrow">Recently added</p>
                <h2 className="section-subheading" id="latest-uploads-title">
                  Latest uploads
                </h2>
              </div>
              <Link href="/documents">View all documents</Link>
            </div>
            <ul className="dashboard-upload-list">
              {latestDocuments.map((document) => (
                <li className="dashboard-upload glass-panel" key={document.id}>
                  <div className="dashboard-upload-copy">
                    <h3 className="document-filename" title={document.filename}>
                      {document.filename}
                    </h3>
                    <p className="helper-text">
                      {formatUploadDate(document.created_at)} · {document.page_count}{" "}
                      {document.page_count === 1 ? "page" : "pages"}
                    </p>
                    {document.failure_reason && (
                      <p className="dashboard-failure-reason">
                        Failure reason: {document.failure_reason}
                      </p>
                    )}
                  </div>
                  <span className={`status-badge status-${statusKind(document.status)}`}>
                    {statusLabel(document.status)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
