# AI Knowledge Assistant

A local-first RAG web app for uploading PDFs, searching personal documents, and asking questions with page-level citations.

## Milestones

1. **M1 — Local application foundation:** monorepo, FastAPI health endpoint, Next.js starter, Neon/pgvector connectivity.
2. **M2 — Backend foundation:** Python 3.12, application configuration, database models and migrations, safe API errors, AI interfaces and test fakes.
3. **M3 — Authentication:** email/password signup and login, JWT access tokens, and authenticated current-user dependency.
4. **M4 — PDF upload and ingestion:** validate uploads, extract document text and page metadata, and track processing state.
5. **M5 — Embeddings and vector search:** generate/store embeddings and search ready document chunks with user-scoped cosine similarity.
7. **M7 — Cited chat:** answer questions from retrieved context with source/page citations.
6. **M6 — Retrieval tuning:** evaluate and improve search relevance over user-scoped document chunks.
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

### Embeddings and vector search (M5)

The current Gemini Embedding 2 model is configured by `GEMINI_EMBEDDING_MODEL`
and `GEMINI_EMBEDDING_DIMENSION`; the project defaults to 768 dimensions to
match the existing `VECTOR(768)` column. Configure `GEMINI_API_KEY` in the
root `.env` file. The API does not fail to start without this key, but document
embeddings will remain retryable and search will be unavailable until it is
configured. Batches default to 16 inputs, retry transient provider failures
with bounded exponential backoff, and persist user-scoped cache entries.

`POST /documents/{id}/retry-embedding` retries only chunks that lack an
embedding. `POST /search` accepts `{"query":"...","top_k":5}` and returns
user-scoped, cosine-ranked chunks from ready documents. `SEARCH_MAX_TOP_K`
defaults to 20; `SEARCH_MIN_SIMILARITY` defaults to 0.0. The M2 cosine HNSW
index is reused. Embedding failures preserve the uploaded file and extracted
chunks and mark the document `embedding_failed`.

For manual retrieval-threshold measurement, start the API and prepare a UTF-8
text file with one question per line, labelled `relevant:` or `offtopic:`. Run
the tool from `backend`; it prompts for the test account credentials and does
not print question text, document chunks, keys, or tokens:

```powershell
python .\scripts\retrieval_scores.py --document-id <document-uuid> --questions-file C:\path\to\questions.txt
```

The tool measures only the selected user's selected document and prints the
top-five similarity scores and page numbers per question, then min/max top-one
scores by label. It requests a `-1.0` similarity cutoff to measure the full
cosine-score range, without changing the configured default. `/search` also
accepts optional `document_ids` and `min_similarity`; omitted `min_similarity`
continues to use `SEARCH_MIN_SIMILARITY`.

The M5 migration changes document status validation, adds chunk model
provenance, and creates the embedding cache. Generate its SQL for review before
any database change:

```powershell
Set-Location backend
python -m alembic upgrade head --sql
```

Vector integration tests use only `TEST_DATABASE_URL`, which must point to a
disposable PostgreSQL + pgvector database with the approved migrations already
applied. They refuse to run if it resolves to the same database as
`DATABASE_URL`, and skip with a clear message if it is absent. The suite does
not apply migrations or DDL automatically. Run SQLite/fake-based tests with:

```powershell
python -m pytest -m "not postgres_vector"
```

After separately approving and preparing the disposable test database, run
vector tests with:

```powershell
python -m pytest -m postgres_vector
```

For an optional manual Gemini smoke test, start the API with the local
`.env` configuration and use a small synthetic PDF:

```powershell
python .\scripts\gemini_smoke.py --pdf C:\path\to\synthetic.pdf
```

The script prompts for login credentials and a search query without printing
credentials or API keys. **Do not upload personal documents while testing with
the real Gemini API.**

Alembic migrations are reviewed before they are applied. From `backend`, generate the SQL without connecting to a database:

```powershell
python -m alembic upgrade head --sql
```

Do not apply a migration to Neon until its generated SQL has been reviewed and explicitly approved.

### Cited chat (M7; delivered before M6 retrieval tuning)

`POST /chat` requires a bearer token and accepts a nonblank `question` plus an
optional `document_ids` list. Retrieval uses the same user-scoped cosine search
as `/search`; requested document IDs are filtered together with the authenticated
user ID. If no chunks meet `SEARCH_MIN_SIMILARITY`, chat returns
`I could not find this in your documents.` without calling Gemini.

The answer must cite retrieved chunks with labels such as `[1]`. The API drops
citation labels that do not match retrieved chunks and returns citations with
document name, page, and a snippet capped at 300 characters. Document text is
passed as delimited untrusted data; system instructions tell the model to ignore
instructions inside document text. The request size, retrieved chunk count,
context size, output tokens, timeout, and retry delays are bounded by the
`GEMINI_CHAT_MODEL` and `CHAT_*` settings in `.env.example`.

The default model is `gemini-3.8-flash`. Google lists it as a stable model with
a 1,048,576-token input limit and 65,536-token output limit ([official model
documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash));
the app defaults its own output cap to 2,048 tokens and uses low thinking.
Google lists standard input/output as free of charge on the Free tier, but rate
limits vary by project and account; check the current limits in Google AI
Studio. The API retries transient 429/5xx errors with bounded backoff and
respects `Retry-After` up to the configured cap.

An optional manual smoke test uploads a synthetic PDF and sends a real chat
request through the running API:

```powershell
python .\scripts\gemini_chat_smoke.py --pdf C:\path\to\synthetic.pdf
```

The script requires a question matching the PDF well enough to retrieve a
chunk. It reports a clear model-name error if Google returns 404. It does not
print API keys or full chunk text. Pytest uses fakes and never calls Gemini.
There is currently **no per-user rate limit** on `/chat`; adding one is planned
for M9 security and reliability hardening. Do not send sensitive documents to
the Gemini API when using a Free-tier project.

M7 is intentionally delivered before M6 so the existing retrieval can support
the first cited-chat workflow; M6 retrieval relevance evaluation remains
pending.

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
