## Deploy

### Vercel (CLI)
Use the production environment when pulling configuration and then trigger a production deployment:

```bash
vercel pull --yes --environment=production --token "$VERCEL_TOKEN"
vercel deploy --prod --token "$VERCEL_TOKEN"
```

### Render (deploy hook)
Trigger a deployment via the configured webhook:

```bash
curl -X POST "$RENDER_DEPLOY_HOOK_URL"
```

For the backend service, run the migration bootstrap script before starting
Uvicorn. This will stamp the base migration (`0001_initial`) if the
`alembic_version` table is missing, then upgrade to head:

```bash
python scripts/bootstrap_migrations.py
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

The Render start command should chain the bootstrap script and Uvicorn in one
command. If Render reports Alembic “multiple head revisions”, resolve it by
merging the heads into a single revision before deploying.

### Stripe environment variables
Configure Stripe keys in the hosting dashboards:

* **Render (backend)** → Environment → add `STRIPE_API_KEY=<secret>`
* **Vercel (frontend)** → Environment → add `VITE_STRIPE_PUBLISHABLE_KEY=<publishable>`

Ensure `STRIPE_API_KEY` does **not** start with `mk_` in production to avoid mock behavior.
