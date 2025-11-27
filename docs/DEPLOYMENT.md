# Deployment Baseline (Phase 0)

This document captures the current production topology so the upcoming refactor
does not regress any hosting quirks.

## Cloudflare

| Record | Type  | Target                                 | Proxy |
|--------|-------|----------------------------------------|-------|
| `@`    | A     | `76.76.21.21` (Vercel edge)            | On    |
| `app`  | CNAME | `<vercel-deployment>.vercel.app`       | On    |
| `www`  | CNAME | `f4a7529fdd483210.vercel-dns-017.com`  | On (Redirect rule to `https://app.libertyplacehoa.com`) |
| `api`  | CNAME | `libertyplacehoa.onrender.com`         | Off (DNS only) |

- Redirect Rule: `http.host eq "www.libertyplacehoa.com"` → `https://app.libertyplacehoa.com/$1`
- `api.libertyplacehoa.com` must stay DNS-only so Render’s TLS certificate works.

## Vercel (frontend)

- Project root: `frontend/`
- Build command: `npm run build`
- Output directory: `frontend/dist`
- SPA routing handled via `frontend/vercel.json` (`/(.*)` → `/index.html`).
- Environment variable `VITE_API_URL` must match `https://api.libertyplacehoa.com`.
- After repository renames, verify Vercel is pointed at the current Git repo; a stale pointer previously served old code.

## Render (backend)

- Service name: `hoa-backend`
- Region: Oregon (`gcp-us-west1`)
- Build command: `pip install -r requirements.txt`
- Start command:
  ```bash
  alembic -c backend/alembic.ini upgrade head &&
  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
  ```
- Important env vars:
  - `DATABASE_URL` (managed PostgreSQL)
  - `FRONTEND_URL=https://app.libertyplacehoa.com`
  - `API_BASE=https://api.libertyplacehoa.com`
  - SMTP: `EMAIL_BACKEND=smtp`, `EMAIL_HOST=smtp.sendgrid.net`, `EMAIL_PORT=587`,
    `EMAIL_HOST_USER=apikey`, `EMAIL_HOST_PASSWORD=<SendGrid key>`,
    `EMAIL_USE_TLS=true`, `EMAIL_FROM_ADDRESS=admin@libertyplacehoa.com`
  - Storage: `FILE_STORAGE_BACKEND=local` (Cloudflare serves `/uploads`)

**Cold start**: Render’s free dyno sleeps after ~15 min. Expect the first request to
take up to a minute. Consider adding a ping monitor or upgrading the plan.

**Health/diagnostics**: `/health` is safe for uptime checks. `/system/runtime`
(SYSADMIN) returns sanitized runtime config to debug env drift without shell
access. GitHub Actions runs Alembic before pytest so `audit_logs` always exists.

## Diagnostics

- Admin-only endpoint `/system/runtime` (added in this phase) outputs anonymized
  runtime settings so ops can confirm environment drift without shell access.

## Things to watch

- SPA rebuilds must always include the `vercel.json` rewrite, otherwise deep links
  404 on refresh.
- Cloudflare redirect targets must never include duplicated protocols
  (`https://https://app…`), or browser history is corrupted.
- SMTP failures currently bubble to the audit log—Render logs are the source of truth.

This baseline should be updated whenever hosting or DNS changes. It will be
referenced throughout the refactor to ensure behavior parity.
