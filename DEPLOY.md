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

### Stripe environment variables
Configure Stripe keys in the hosting dashboards:

* **Render (backend)** → Environment → add `STRIPE_API_KEY=<secret>`
* **Vercel (frontend)** → Environment → add `VITE_STRIPE_PUBLISHABLE_KEY=<publishable>`

Ensure `STRIPE_API_KEY` does **not** start with `mk_` in production to avoid mock behavior.
