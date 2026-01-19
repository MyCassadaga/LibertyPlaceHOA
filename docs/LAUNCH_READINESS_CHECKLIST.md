# Launch Readiness Checklist

> Goal: staged readiness checks with clear “Definition of Done” (DoD) per stage. Use placeholders where commands/endpoints are unknown.

## Stage 0 — Repo compiles/builds

**DoD**
- Backend dependencies install without errors.
- Frontend dependencies install without errors.
- Lint/test steps (if any) complete or are explicitly waived.

**Checklist**
- [ ] `pip install -r requirements.txt`
- [ ] `cd frontend && npm install`
- [ ] (Optional) `pytest` or existing CI checks

## Stage 1 — Local run (frontend + backend) with sample env

**DoD**
- Backend starts locally and serves `/health`.
- Frontend starts locally and can reach the backend API.
- `.env.template` values are copied into working `.env` files.

**Checklist**
- [ ] `cp .env.template .env`
- [ ] `cp frontend/.env.template frontend/.env` (if needed)
- [ ] `alembic upgrade head`
- [ ] `uvicorn backend.main:app --reload --port 8000`
- [ ] `cd frontend && npm run dev`

## Stage 2 — DB migrations safe and repeatable (Render bootstrap path)

**DoD**
- Render startup path succeeds: `python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- New DB boots cleanly with Alembic head.
- No manual intervention needed to start the service.

**Checklist**
- [ ] `python scripts/bootstrap_migrations.py reconcile`
- [ ] Confirm Alembic head matches `backend/migrations`.

## Stage 3 — Deployed smoke tests + health endpoints

**DoD**
- Backend `/health` returns 200 on deployed domain.
- Frontend loads and can authenticate (if enabled).
- CORS configured for deployed frontend URL.

**Checklist**
- [ ] GET `https://<backend-domain>/health`
- [ ] Load `https://<frontend-domain>`
- [ ] Confirm login and a basic API call

## Stage 4 — Email integration test plan (Google Workspace)

**DoD**
- SMTP test plan documented and verified against a test inbox.
- Email backend configuration confirmed in deployment environment.

**Checklist**
- [ ] Configure SMTP credentials in environment
- [ ] Send a test email via the API or admin action
- [ ] Validate SPF/DKIM alignment (if applicable)

## Stage 5 — Observability + error reporting

**DoD**
- Monitoring/alerting endpoints defined.
- Error logs are accessible and actionable.
- Ownership for alerts and on-call response is documented.

**Checklist**
- [ ] Identify existing logging/monitoring provider (placeholder if unknown)
- [ ] Define alert thresholds for `/health` failures
- [ ] Confirm log access for backend and frontend deployments
