# Phase 4 (Polish & Ops) Quick Checklist

Use this to validate the app before calling Phase 4 done or pushing to prod.

## Deploy & DNS sanity
- Frontend (Vercel): `frontend/vercel.json` rewrite `/(.*)` → `/index.html`; `VITE_API_URL=https://api.libertyplacehoa.com`.
- Backend (Render): start command runs Alembic then `uvicorn backend.main:app`; free plan idles after ~15 min (expect first-request cold start).
- Cloudflare: `api.libertyplacehoa.com` DNS-only (no proxy); `app.`/`www.` proxied; redirect `www` → `https://app.libertyplacehoa.com/$1` without double `https://`.

## Environment keys (prod)
- API: `FRONTEND_URL`, `API_BASE`, `DATABASE_URL`, `EMAIL_BACKEND=smtp`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS=true`.
- Storage: `FILE_STORAGE_BACKEND` (`local` or `s3`), `UPLOADS_PUBLIC_URL` if proxied.
- CORS: `ADDITIONAL_CORS_ORIGINS` for temporary admin hosts.

## Monitoring & diagnostics
- Health: `/health` for uptime checks; `/system/runtime` (SYSADMIN) to verify env drift.
- Logs: structured JSON via pythonjsonlogger when installed; otherwise plain text.
- Optional: set up an external ping (e.g., UptimeRobot) every 10 min to keep Render warm.

## Performance & bundles
- Run Lighthouse (desktop & mobile) against `app.libertyplacehoa.com`: fix red flags for contrast, tap targets, and bundle bloat.
- Large lists (Owners/Violations/ARC): if sluggish at scale, enable server pagination or virtualized rows; table component already supports pagination props if needed.
- WebSocket keepalive enabled for notifications; ensure Cloudflare allows `wss` to `api.` host.

## Accessibility
- Verify skip links, heading order, ARIA labels on forms, and focus outlines. Use axe DevTools or Lighthouse a11y audit.

## Tests & lint
- Backend: `. .venv/bin/activate && pytest tests/test_elections.py` (extend to full suite when available).
- Frontend: `cd frontend && npm run lint`. Add component tests (React Testing Library) for auth and elections when time allows.

## Release steps (manual)
```bash
git status
git add .
git commit -m "Phase 4 polish: docs + websocket keepalive + utc timestamps"
git push origin <branch>
```
