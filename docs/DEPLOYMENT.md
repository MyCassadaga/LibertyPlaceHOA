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

## Render (frontend static site)

- Service type: Static Site
- Root directory: `frontend/`
- Build command: `npm ci && npm run build`
- Publish directory: `dist`
- Environment variables (build-time):
  - `VITE_API_URL=https://api.libertyplacehoa.com`
  - `VITE_STRIPE_PUBLISHABLE_KEY=<public key>` (optional)
- SPA routing: add a rewrite in Render or keep `frontend/vercel.json` if reusing the same config (rewrite `/*` → `/index.html`).

## Render (backend)

- Service name: `hoa-backend`
- Region: Oregon (`gcp-us-west1`)
- Build command: `pip install -r requirements.txt`
- Start command:
  ```bash
  bash -lc "python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
  ```
- Database:
  - `DATABASE_URL` must be set in the Render dashboard (Neon is the source of truth; no Render-managed database resource).
- SMTP:
  - Google Workspace SMTP is required; SendGrid is not used.
  - Use the standardized SMTP env var contract below and set values in the Render dashboard (backend + cron).

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

## Render env var checklist

### Backend web service (`hoa-backend`)

- `DATABASE_URL=<neon connection string>` (required; set in Render dashboard)
- `FRONTEND_URL=https://app.libertyplacehoa.com`
- `API_BASE=https://api.libertyplacehoa.com`
- `ADDITIONAL_TRUSTED_HOSTS=libertyplacehoa.onrender.com,api.libertyplacehoa.com`
- SMTP (Google Workspace):
  - `SMTP_HOST=smtp.gmail.com`
  - `SMTP_PORT=587`
  - `SMTP_USERNAME=<workspace user>`
  - `SMTP_PASSWORD=<app password>`
  - `SMTP_USE_TLS=true`
  - `SMTP_FROM_EMAIL=admin@libertyplacehoa.com`
  - `SMTP_FROM_NAME=Liberty Place HOA`
  - Legacy aliases required by current backend config (set equal to `SMTP_FROM_*`):
    - `EMAIL_FROM_ADDRESS=admin@libertyplacehoa.com`
    - `EMAIL_FROM_NAME=Liberty Place HOA`
- Storage:
  - `FILE_STORAGE_BACKEND=local`

### Cron job (`hoa-autopay`)

- Set the **same** env vars as `hoa-backend`, including `DATABASE_URL` and SMTP keys.

### Frontend static site (`hoa-frontend`)

- `VITE_API_URL=https://api.libertyplacehoa.com`
- `VITE_STRIPE_PUBLISHABLE_KEY=<public key>` (optional)

This baseline should be updated whenever hosting or DNS changes. It will be
referenced throughout the refactor to ensure behavior parity.
