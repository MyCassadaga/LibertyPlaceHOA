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

For the backend service, run the migration reconciliation script before starting
Uvicorn. This checks for the `alembic_version` table and safely stamps the best
matching revision when the schema exists but Alembic state is missing, then
upgrades to head:

```bash
python scripts/bootstrap_migrations.py
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

The Render start command should chain the reconciliation script and Uvicorn in one
command. If Render reports Alembic “multiple head revisions”, resolve it by
merging the heads into a single revision before deploying.

### Migration diagnostics
When troubleshooting migrations, run the diagnostics command and compare against
the SQL checks below:

```bash
python scripts/bootstrap_migrations.py diagnostics
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini history --verbose
```

SQL checks (Postgres):

```sql
SELECT EXISTS (
  SELECT 1
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'alembic_version'
) AS alembic_version_exists;

SELECT EXISTS (
  SELECT 1
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'user_roles'
) AS user_roles_exists;

SELECT EXISTS (
  SELECT 1
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'budgets'
) AS budgets_exists;

SELECT EXISTS (
  SELECT 1
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'arc_requests'
    AND column_name = 'decision_notified_at'
) AS arc_requests_decision_notified_at_exists;
```

### Stripe environment variables
Configure Stripe keys in the hosting dashboards:

* **Render (backend)** → Environment → add `STRIPE_API_KEY=<secret>`
* **Vercel (frontend)** → Environment → add `VITE_STRIPE_PUBLISHABLE_KEY=<publishable>`

Ensure `STRIPE_API_KEY` does **not** start with `mk_` in production to avoid mock behavior.
