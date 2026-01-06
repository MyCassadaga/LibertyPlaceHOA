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

For the backend service, ensure the Render start command runs migrations and
binds to Render’s provided port (for example, `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`).
If Render reports Alembic “multiple head revisions”, resolve it by merging
the heads into a single revision before deploying.

### Stripe environment variables
Configure Stripe keys in the hosting dashboards:

* **Render (backend)** → Environment → add `STRIPE_API_KEY=<secret>`
* **Vercel (frontend)** → Environment → add `VITE_STRIPE_PUBLISHABLE_KEY=<publishable>`

Ensure `STRIPE_API_KEY` does **not** start with `mk_` in production to avoid mock behavior.
