# Platform Consolidation Memo (Evidence-Based)

> Scope: document-only options. No infrastructure changes are proposed or executed here.

## Current provider footprint (evidence in repo)

- **Render (backend hosting + migrations):** `render.yaml` defines the `hoa-backend` service and the `bootstrap_migrations.py` + `uvicorn` startup path.
- **Vercel (frontend hosting):** `frontend/vercel.json` configures the static build/rewrites for the React app.
- **Cloudflare (DNS + routing guidance):** `docs/DEPLOYMENT.md` and `README.md` document DNS/proxy expectations.
- **Google Workspace (SMTP):** `docs/DEPLOYMENT.md` references `smtp.gmail.com` for SMTP.
- **Neon (possible Postgres provider):** `backend/config.py` includes a reference to Neon-style connection strings.

If any of the above are stale, treat this memo as a starting point and update it after confirming current production usage.

## Consolidation options

### Option A — Keep Vercel + Render + DB provider, simplify Cloudflare usage

**Pros**
- Minimal change to deploy workflows.
- Keeps existing frontend/backend separation.
- Reduces DNS/proxy complexity to the minimum required.

**Cons**
- Still multi-vendor; coordination across providers remains.
- TLS/DNS behavior must be managed across Cloudflare + Render/Vercel.

**What must change**
- DNS records/rules only (tighten to a minimal set).
- Ensure `FRONTEND_URL`, `API_BASE`, and `ADDITIONAL_TRUSTED_HOSTS` match deployed domains.
- Confirm auth callbacks and webhook URLs (if any) match the chosen canonical domains.

**Risk level**: Low

**Next 3 steps**
1. Inventory existing DNS records and remove unused entries.
2. Confirm the canonical frontend + backend domains and update env vars.
3. Validate `/health` and core flows after DNS changes.

### Option B — Move more to Cloudflare (Pages/Workers) where feasible

**Pros**
- Potentially fewer vendors if Cloudflare can host the frontend.
- Unified DNS + edge configuration.

**Cons**
- Requires a new deployment path for the frontend.
- Worker/edge limitations may require changes in build output or routing.

**What must change**
- Replace Vercel deployment with Cloudflare Pages.
- Validate rewrites and SPA routing in the new hosting environment.
- Update DNS and environment variables accordingly.

**Risk level**: Medium

**Next 3 steps**
1. Prototype a Cloudflare Pages deployment of `frontend/`.
2. Verify SPA routing and API base URL configuration.
3. Plan a cutover window and rollback path.

### Option C — Single-vendor consolidation (only if feasible)

**Pros**
- Simplifies billing, credentials, and operational ownership.
- Reduces cross-provider config drift.

**Cons**
- Largest operational change; highest risk.
- Requires validating service parity (build + runtime + database + email).

**What must change**
- Migrate frontend hosting to the chosen vendor.
- Align backend hosting and DB provisioning to the same vendor.
- Update DNS, auth callbacks, and webhook targets.

**Risk level**: High

**Next 3 steps**
1. Identify the single vendor that can host frontend + backend + DB.
2. Prove a staging environment end-to-end before cutover.
3. Execute a phased migration with a rollback plan.
