# Project Reset Guide

> Purpose: a “start here” guide for re-onboarding and stabilizing the project without changing runtime behavior.

## What this repo contains

- A FastAPI + SQLAlchemy backend in `backend/`.
- A Vite + React frontend in `frontend/`.
- Render deployment config in `render.yaml`.
- Vercel frontend config in `frontend/vercel.json`.

For a generated map of the current repo structure, see [`docs/REPO_TOUR.md`](REPO_TOUR.md).

## Minimum path to running locally end-to-end

> Use these steps as the shortest path to a working local setup. Replace placeholder values with your own environment settings where required.

### Backend (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.template .env
alembic upgrade head
python backend/manage_create_admin.py --email admin@example.com --password changeme
uvicorn backend.main:app --reload --port 8000
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

### One-step local launch (if you want both servers)

```bash
python3 scripts/start_dev.py
```

## Minimum path to deployed and healthy

1. **Render backend start command must remain:**
   ```bash
   python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```
2. **Frontend deploy target:** Vercel builds from `frontend/` via `frontend/vercel.json`.
3. **DNS routing:** follow Cloudflare DNS guidance in `docs/DEPLOYMENT.md`.
4. **Health check:** `/health` endpoint should return success from the backend once migrations are applied.

## Stop the bleeding (no refactors)

Focus only on the smallest fixes needed to stabilize the system:

1. **Build/compile first:** backend dependencies, frontend build, and CI steps must pass.
2. **Migration safety:** ensure `bootstrap_migrations.py` succeeds and Alembic head matches the DB.
3. **Environment drift:** reconcile `.env.template`, Render env vars, and frontend `.env.template`.
4. **Deploy parity:** confirm local behavior matches Render + Vercel deploys (same URLs, CORS, and API base).

## Known unknowns checklist

- [ ] Confirm current production database provider and connection string format.
- [ ] Confirm which email backend is active in production (SMTP/SendGrid/other).
- [ ] Verify `FRONTEND_URL`, `API_BASE`, and `ADDITIONAL_TRUSTED_HOSTS` values in production.
- [ ] Confirm the canonical domain routing (Cloudflare rules + cert expectations).
- [ ] Identify where secrets are stored (Render dashboard, Vercel secrets, etc.).
- [ ] Confirm health check endpoints used by monitoring.
- [ ] Verify whether any background jobs beyond `scripts/run_autopay.py` exist.
