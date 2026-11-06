# Production configuration and deployment runbook

This runbook is for the first public demo launch. It is intentionally
manual: do not paste secrets into Git, Vercel public variables, chat, or shell
history. The repository does not claim that production is deployed or that
any provider setting has been verified.

## Recommended production topology

Create a separate Neon **project**, not merely a branch of the existing test
project. A separate project gives production a clean user set, independent
credentials, independent deletion/restore boundaries, and less risk of
accidentally running a destructive test against production. A production
branch is reasonable later when branch limits or cost make a project
impractical, but it is not the safest first launch choice.

The production database must use Neon’s direct, non-pooled hostname for
Alembic migrations. Keep the pooled URL for application traffic only if the
chosen Neon setup recommends it. From a laptop, with the direct URL entered
privately at a prompt:

```powershell
Set-Location backend
$secureUrl = Read-Host "Production direct DATABASE_URL" -AsSecureString
$urlPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUrl)
try {
  $env:DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($urlPtr)
  python -m alembic current
  python -m alembic upgrade head
  python -m alembic current
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($urlPtr)
  Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
}
```

The expected final revision is `0004` (or a later revision if one is added
before launch). `alembic current` prints the revision, not the database URL;
verify the revision output only. Run this once from the laptop against the
new production project, never against the existing test database. Review the
generated SQL first if a later migration is introduced.

## Secrets and provider boundaries

Create fresh production values:

- a new random `JWT_SECRET_KEY` of at least 32 bytes;
- a new Neon production database password and direct/pooled connection URLs;
- a production Gemini API key created for the intended project and quota.

Enter these only in Render’s encrypted secret environment variables. Do not
put them in the repository, Vercel variables, `NEXT_PUBLIC_*` variables, or
the browser. Vercel only needs the public API URL; the backend owns the Gemini
key and database credentials.

For a no-card Gemini free-tier launch, verify the current Google AI Studio
terms, model availability, quotas, rate limits, and data-use setting yourself
before launch. Free-tier availability and limits are model/account/region
dependent, can change, and may have different data-use terms from paid
accounts. Treat uploaded text sent for embeddings and answers as disclosed in
the privacy wording; do not upload sensitive, confidential, or personal data.

## Render backend service

### Choice: native Python deploy for the first free service

Use Render’s native Python service for the first launch. It makes the required
`$PORT` start command explicit, avoids an unverified image build, and keeps
the free service configuration easy to inspect. The existing
[backend/Dockerfile](../backend/Dockerfile) is a valid alternative when a
container workflow is preferred, but its current command listens on `8000`
instead of interpolating `$PORT`; use native deployment for this runbook or
make that Dockerfile change in a separate approved step.

Render settings:

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Runtime | Python 3.12 |
| Build command | `python -m pip install .` |
| Start command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Instances | 1 |
| Workers | Do not add `--workers`; keep one process |
| Persistent disk | None when `FILE_STORAGE_BACKEND=none` |

Do not run migrations from the Render start command. Run the explicit Alembic
step above from the laptop with the direct URL, then start the service.

### Render environment variables

Set secret values in Render’s secret store. The examples below are safe
non-secret examples or proposed launch values; replace the API hostname with
the exact backend URL Render assigns.

| Variable | Purpose | Launch value/example |
|---|---|---|
| `DATABASE_URL` | Runtime Neon connection | secret pooled or provider-recommended URL |
| `JWT_SECRET_KEY` | Signs access tokens | fresh secret, not a placeholder |
| `GEMINI_API_KEY` | Gemini embeddings/chat | fresh secret, not in Vercel |
| `CORS_ORIGINS` | Exact browser origin | `["https://YOUR-VERCEL-PRODUCTION-DOMAIN"]` |
| `FILE_STORAGE_BACKEND` | Discard original PDFs | `none` |
| `SIGNUP_ENABLED` | Disable public accounts | `false` |
| `AI_FEATURES_ENABLED` | Gemini kill switch | `true` only when the key/model is ready |
| `DEMO_MODE` | Enable seeded read-only demo | `true` after seeding |
| `DEMO_USER_EMAIL` | Demo account identity | `demo@example.com` or chosen non-personal address |
| `DEMO_DOCUMENT_ID` | Explicit seeded document | UUID printed by the seed command |
| `DEMO_SESSION_EXPIRE_MINUTES` | Demo token lifetime | `15` |
| `DEMO_MAX_DOCUMENTS_PER_USER` | Demo document cap | `3` |
| `DEMO_MAX_PDF_PAGES` | Demo upload page cap | `50` (uploads remain disabled) |
| `DEMO_MAX_USERS` | Safety cap | `100` |
| `DEMO_MAX_DOCUMENTS` | Safety cap | `300` |
| `DEMO_SESSION_REQUESTS_PER_MINUTE` | Generous global issuance cap | `120` |
| `DEMO_SESSION_REQUESTS_PER_DAY` | Generous global issuance cap | `2000` |
| `DEMO_CHAT_REQUESTS_PER_MINUTE` | Per-demo-session chat cap | `5` |
| `DEMO_CHAT_REQUESTS_PER_DAY` | Per-demo-session chat cap | `50` |
| `DEMO_SEARCH_REQUESTS_PER_MINUTE` | Per-demo-session search cap | `10` |
| `DEMO_SEARCH_REQUESTS_PER_DAY` | Per-demo-session search cap | `100` |
| `DEMO_CHAT_GLOBAL_REQUESTS_PER_DAY` | Global Gemini chat budget | `200` |
| `DEMO_SEARCH_GLOBAL_REQUESTS_PER_DAY` | Global embedding/search budget | `500` |
| `GEMINI_CHAT_MODEL` | Primary chat model | model available to the key |
| `GEMINI_CHAT_FALLBACK_MODEL` | Optional fallback | empty until verified |
| `TRUSTED_PROXY_CIDRS` | Trusted proxy networks | empty: `[]` |

The conservative demo chat/search defaults above intentionally assume the
free Gemini quota is unknown. The issuance cap is global and generous because
an empty `TRUSTED_PROXY_CIDRS` can make all visitors share one proxy IP. Once
issued, opaque demo-session identities carry the real per-session limits.

The counters are in memory. Render sleep/restart clears them, so “daily” is a
best-effort per-process budget, not a durable daily quota. One Render instance
avoids cross-instance disagreement but does not survive restarts. If the demo
becomes popular, add a database-backed counter keyed by UTC date, operation,
and session/global scope, with an atomic upsert/increment and expiry policy;
that is intentionally not implemented here.

## Vercel Hobby frontend

Create the Vercel project with:

- Root Directory: `frontend`;
- Framework preset: Next.js;
- Install command: `npm ci --legacy-peer-deps`;
- Build command: `npm run build`;
- `NEXT_PUBLIC_API_URL`: the exact HTTPS Render backend URL, set before the
  production build and redeploy after changing it.

The exact Vercel production domain is deployment-specific and is not present
in this repository. Copy the production domain shown by Vercel exactly into
Render’s `CORS_ORIGINS`, without a trailing slash or path. Do not use a
preview domain as the production CORS origin.

The repository sets `output: "standalone"` in
[frontend/next.config.ts](../frontend/next.config.ts). The existing
[frontend/Dockerfile](../frontend/Dockerfile) uses that output. Vercel’s normal
Next.js build can also use the `frontend` root and its default deployment
output; do not assume the Docker standalone layout is required by Vercel.

## Manual production seed

1. Create the clean production Neon project and apply migrations from the
   laptop using the direct URL procedure above.
2. Confirm the production backend secrets are present in Render, but leave
   `DEMO_MODE=false` until the document exists.
3. From the repository’s `backend` directory, enter the production URL into a
   hidden prompt and run the committed, idempotent seed script. This avoids
   putting the URL in shell history or chat:

```powershell
Set-Location backend
$secureUrl = Read-Host "Production direct DATABASE_URL" -AsSecureString
$urlPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUrl)
try {
  $env:DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($urlPtr)
  python .\scripts\seed_demo.py
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($urlPtr)
  Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
}
```

Expected output includes either a newly seeded document ID or a message that
the demo document already exists. It sends the sample’s extracted text to the
configured Gemini embedding model once; it does not call Gemini on each demo
visit. Copy the reported UUID into Render’s `DEMO_DOCUMENT_ID`, set
`DEMO_MODE=true`, and redeploy/restart the service. Re-running the command
must report the existing document rather than create a duplicate.

Rollback: set `DEMO_MODE=false`, then use an authenticated database session or
the following reviewed maintenance SQL to delete the demo user and its
document. Substitute the exact demo email and document UUID privately; do not
put real values in Git or chat:

```sql
BEGIN;
DELETE FROM embedding_cache
WHERE user_id = (SELECT id FROM users WHERE lower(trim(email)) = lower('demo@example.com'));
DELETE FROM chunks
WHERE document_id = '00000000-0000-0000-0000-000000000000'::uuid;
DELETE FROM documents
WHERE id = '00000000-0000-0000-0000-000000000000'::uuid
  AND user_id = (SELECT id FROM users WHERE lower(trim(email)) = lower('demo@example.com'));
DELETE FROM users
WHERE lower(trim(email)) = lower('demo@example.com');
COMMIT;
```

Run the deletes only after confirming the email and UUID in a transaction. If
the schema has additional dependent rows or does not cascade, delete those
rows first. Verify the user, document, chunks, and matching
`embedding_cache` rows are gone before deleting the project or credentials.

## Measurement plan

- **Neon storage:** upload the sample PDF, record its document UUID, then run
  the SQL in [README.md](../README.md#measuring-real-neon-storage). It reports
  actual table/index sizes and logical payloads, including `embedding_cache`;
  divide shared relation allocation carefully because cache rows can be
  reused.
- **Render memory:** use the service Metrics/Graphs view during idle, cold
  start, seed-independent demo traffic, and chat. Record peak RSS/working-set
  memory and compare it with the instance limit. Do not treat the old 70–120 MB
  estimate as measured.
- **Instance hours:** record the Render usage/instance-hours dashboard after
  the observation period; sleep/restart behavior affects the number.
- **Cold start:** issue a request after the service has slept and measure
  `curl.exe -sS -o NUL -w "DNS=%{time_namelookup} CONNECT=%{time_connect} START=%{time_starttransfer} TOTAL=%{time_total}\n" https://BACKEND/health`.
- **First request timeout:** repeat the same command against `/health` and a
  harmless authenticated read endpoint after sleep. Record HTTP status and
  total time, and check Render logs for startup/provider errors. Do not infer
  Gemini latency from `/health`; it does not call Gemini.

## Launch checklist and rollback

Before announcing the URL:

- confirm `GET /health` is 200;
- open the real Vercel landing page and allow the first page to warm up;
- click **Try demo**;
- run demo chat and confirm citations point to the sample document;
- exercise a controlled demo 429 and confirm the friendly tomorrow message;
- verify a browser request from the exact production domain passes CORS;
- confirm uploads/signup are disabled and `FILE_STORAGE_BACKEND=none` is set;
- check Render logs and the measured Neon/Render dashboards.

If Gemini returns 503/504, leave `AI_FEATURES_ENABLED=false` if the provider
is unavailable, show the friendly service-unavailable response, and inspect
the model/key/quota configuration. Do not enable an unverified fallback model.
If the backend is unhealthy, set `DEMO_MODE=false` and/or
`AI_FEATURES_ENABLED=false`, revert the Render service to the last known-good
commit/configuration, and keep the Vercel frontend pointed at the known-good
backend. If data must be removed, disable the demo first and use the reviewed
rollback procedure above.

## Still unverified

The latest commits’ CI status has not been verified here. Gemini free-tier
quotas, current data-use terms, exact model availability, Render’s proxy
forwarding behavior, Neon’s current free storage limit, Render memory, Render
instance hours, production cold-start timing, and first-request timeout timing
must all be checked in their respective dashboards/provider documentation.
