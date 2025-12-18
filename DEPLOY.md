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
