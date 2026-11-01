# AI Knowledge Assistant

A local-first RAG web app for uploading PDFs, searching personal documents, and asking questions with page-level citations.

## Milestones

1. **M1 — Local application foundation:** monorepo, FastAPI health endpoint, Next.js starter, Neon/pgvector connectivity.
2. **M2 — Backend foundation:** Python 3.12, application configuration, database models and migrations, safe API errors, AI interfaces and test fakes.
3. **M3 — Authentication:** email/password signup and login, JWT access tokens, and authenticated current-user dependency.
4. **M4 — PDF upload and ingestion:** validate uploads, extract document text and page metadata, and track processing state.
5. **M5 — Embeddings:** chunk extracted text and generate/store embeddings with the configured provider.
6. **M6 — Vector retrieval:** user-scoped similarity search over document chunks.
7. **M7 — Cited chat:** answer questions from retrieved context with source/page citations.
8. **M8 — Frontend workflows:** authentication, document management, upload progress, search and chat UI.
9. **M9 — Security, reliability and deployment:** operational hardening, observability, deployment configuration and recovery.
10. **M10 — Evaluation and production readiness:** end-to-end verification, quality evaluation, performance checks and release readiness.

## M1: Local application foundation

M1 established the monorepo, a FastAPI health endpoint, a Next.js App Router starter, and a Neon PostgreSQL connection check for pgvector. Embeddings, chat, and deployment are later milestones.

### Prerequisites

- Python 3.12
- Node.js and npm
- A Neon PostgreSQL database

### Backend

From the repository root, create and activate a virtual environment:

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -e "backend[dev]"
```

Run the API from the `backend` directory:

```powershell
Set-Location backend
uvicorn app.main:app --reload
```

The health endpoint is available at `http://localhost:8000/health`. Run backend tests from `backend` with `python -m pytest`.

### Authentication (M3)

Set `JWT_SECRET_KEY` to a random secret of at least 32 bytes and configure
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES` in the root `.env` file. The example file
contains placeholders only; replace the JWT key placeholder before starting
the API. Startup fails if the key is missing, shorter than 32 bytes, or a
recognized placeholder. Signup and login return a bearer access token;
send it in the `Authorization: Bearer <token>` header for `GET /auth/me`.
Signup emails must be valid email addresses no longer than 320 characters;
surrounding whitespace is trimmed and addresses are normalized to lowercase.
Signup passwords must be 12–128
characters; passwords are not trimmed. The Swagger schema documents the email
format and password length constraints. Passwords are stored as Argon2id
hashes. Review and apply the M3 Alembic migration before using authentication
against a database.

### PDF documents (M4)

Authenticated users can upload PDFs with `POST /documents` using multipart
field `file`, list their own documents with `GET /documents`, retrieve one with
`GET /documents/{id}`, and delete one with `DELETE /documents/{id}`. Uploads
require a `.pdf` filename, `application/pdf` content type and PDF signature.
Defaults are 10 MiB maximum file size, 200 pages, 900-character chunks and
150-character overlap. Override with `MAX_UPLOAD_SIZE_BYTES`, `MAX_PDF_PAGES`,
`CHUNK_SIZE`, and `CHUNK_OVERLAP`. Local files live under `.local/uploads/`
(ignored by Git). Scanned PDFs without selectable text are marked failed;
OCR is not part of M4.

Alembic migrations are reviewed before they are applied. From `backend`, generate the SQL without connecting to a database:

```powershell
python -m alembic upgrade head --sql
```

Do not apply a migration to Neon until its generated SQL has been reviewed and explicitly approved.

### Frontend

```powershell
Set-Location frontend
npm run dev
```

Run its basic UI tests with `npm test` and create a production build with `npm run build`.

### Neon and pgvector

Copy `.env.example` to `.env` and set `DATABASE_URL` to the connection URL shown by Neon. Keep `.env` private; it is ignored by Git. Then, from `backend`, run:

```powershell
python -m app.database
```

This connects to the configured database and reports whether the `vector` extension is enabled. If it is not, enable it in the Neon SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Project layout

```text
backend/    FastAPI service, database integration, and tests
frontend/   Next.js App Router application and UI tests
.env.example
README.md
```
