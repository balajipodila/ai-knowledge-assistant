# AI Knowledge Assistant

A local-first RAG web app for uploading PDFs, searching personal documents, and asking questions with page-level citations.

## M1: Local application foundation

M1 establishes the monorepo, a FastAPI health endpoint, a Next.js App Router starter, and a Neon PostgreSQL connection check for pgvector. Authentication, PDF ingestion, embeddings, chat, and deployment are later milestones.

### Prerequisites

- Python 3.12 or newer
- Node.js and npm
- A Neon PostgreSQL database

### Backend

From the repository root, create and activate a virtual environment:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -e "backend[dev]"
```

Run the API from the `backend` directory:

```powershell
Set-Location backend
uvicorn app.main:app --reload
```

The health endpoint is available at `http://localhost:8000/health`. Run backend tests from `backend` with `pytest`.

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
