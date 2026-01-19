# Liberty Place HOA Documentation (Consolidated)

## Overview

Liberty Place HOA is a two-tier application:

- **Backend:** FastAPI + SQLAlchemy in `backend/`.
- **Frontend:** Vite + React in `frontend/`.
- **Deployment config:** `render.yaml` (backend), `frontend/vercel.json` (frontend).

Key runtime entry points:
- `backend/main.py` (FastAPI app).
- `scripts/bootstrap_migrations.py` (pre-uvicorn database reconcile).
- `scripts/start_dev.py` (one-step local launch).

## Architecture & Runtime Entry Points

### Render deployment (backend)
- **Service:** `hoa-backend`.
- **Build:** `pip install -r requirements.txt`.
- **Start command:**
  ```bash
  python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
  ```
- **Environment:** `DATABASE_URL` (required), `FRONTEND_URL`, `API_BASE`, `ADDITIONAL_TRUSTED_HOSTS`, `APP_ENV=prod`.
- **Cron job:** `hoa-autopay` runs `python scripts/run_autopay.py` daily at 06:00 UTC and uses the same DB/env.

### Pre-uvicorn bootstrap (`scripts/bootstrap_migrations.py`)
- Requires `DATABASE_URL`; exits if missing.
- Validates SQLAlchemy URL; logs host + database.
- Inspects DB for existing tables and Alembic version state.
- If schema is untracked, bootstrap **refuses to run** to prevent corrupting a non-Alembic DB.
- Reconciles schema with Alembic by stamping or upgrading, then runs `alembic upgrade head` using `backend/alembic.ini`.

### Backend app lifecycle (`backend/main.py`)
- App startup (`lifespan`) ensures:
  - DB tables exist.
  - Default roles/permissions exist.
  - User-role links are backfilled.
  - Billing policy and tiers exist.
  - Notice types are synchronized.
  - Contract renewal reminders, owner/user link backfills, and next-year draft budgets are generated.
  - Notification loop is configured.
- App shutdown attempts an SQLite backup.

### Middleware chain (in code order)
1. `TrustedHostMiddleware` (allowed host headers).
2. `CORSMiddleware` (allowed origins + optional regex).
3. `SecurityHeadersMiddleware` (HSTS, CSP, etc.).
4. `request_context` (request ID).
5. `audit_trail` (logs POST/PUT/PATCH/DELETE to audit logs, excluding `/notifications/ws`).

## Data Layer & Migrations

### Models
- SQLAlchemy models are defined in `backend/models/models.py`.
- Association tables: `user_roles`, `role_permissions`.

### Alembic configuration
- `backend/alembic.ini` sets the migrations script location (`backend/migrations`).
- `backend/migrations/env.py` loads app settings, registers metadata, and uses `render_as_batch` for SQLite.

### Migration graph
- Existing migrations (in order):
  - `0001_baseline_baseline.py`
  - `0002_make_audit_actor_nullable.py`
  - `0003_seed_admin_user.py`
  - `0004_add_template_types.py`
  - `0005_add_workflow_configs.py`
  - `0006_add_two_factor_secret_to_users.py`
  - `0007_add_communication_message_delivery_tracking.py`
  - `0008_fix_message_delivery_tracking_and_backgroundtasks.py`
  - `0009_widen_alembic_version_num.py`

## Auth & Admin

### Admin creation paths
- **CLI:** `backend/manage_create_admin.py` creates a SYSADMIN user (email/password provided).
- **Migration seed:** `0003_seed_admin_user.py` seeds `admin@libertyplacehoa.com` with default password `changeme` and assigns SYSADMIN role (idempotent upsert).
- **Dev seed script:** `scripts/seed_data.py` creates `admin@example.com` with SYSADMIN + BOARD roles.
- **Runtime:** `backend/main.py` does **not** create admin users; it only ensures default roles, permissions, and data relationships.

### JWT security
- JWT secret loads from `JWT_SECRET` (default: `dev-secret-please-change` with a warning if used in production).
- JWTs must include a valid `sub` user ID and token type `access`/unset; otherwise the request is unauthorized.

## Audit Logging

- Audit logs are stored in `audit_logs` via `backend/services/audit.py`.
- `audit_trail` middleware logs all mutating HTTP requests (POST/PUT/PATCH/DELETE) except `/notifications/ws`.
- Actor derivation: bearer token → JWT decode → `sub` user ID lookup; missing/invalid tokens produce `actor_user_id = None`.
- `audit_logs.actor_user_id` is nullable to allow anonymous/system entries.

## Invariants & Operational Guardrails

### Schema/data invariants
1. `roles.name` is unique and non-null; role checks depend on names (e.g., `SYSADMIN`).
2. `permissions.name` is unique and non-null.
3. `users.email` is unique and non-null.
4. `users.role_id` is non-null and must reference a valid role.
5. `user_roles.assigned_at` is non-null.
6. Default roles (`DEFAULT_ROLES`) must exist.
7. Users should have at least one role; missing `user_roles` links are backfilled from the primary role.
8. `audit_logs.actor_user_id` is nullable.
9. Mutating HTTP requests are audited except `/notifications/ws`.
10. JWTs must include a valid `sub` and token type `access`/unset.
11. `JWT_SECRET` default is insecure; set in production.
12. `owners.lot` is unique and non-null.
13. `owners.primary_name` and `owners.property_address` are required.
14. Default billing policy `default` must exist and have expected tier sequences.
15. Notice types must stay in sync with `NOTICE_TYPE_SEED`.
16. DB schema must be empty or Alembic-tracked; bootstrap exits on untracked schemas.

### Change strategy & contract (non-negotiable)
- **Never edit old migrations that may have shipped.**
- **Seeds must be idempotent.**
- **Never hardcode `user_id = 1`.**
- **Satisfy all NOT NULL columns in inserts.**
- **Migrations must work on a brand-new empty database.**
- **Render start command must succeed without manual DB intervention.**

### Required workflow for changes
1. **Phase 0: Understand** — identify impacted areas.
2. **Phase 1: Reproduce** — state exact error/invariant violated.
3. **Phase 2: Minimal Fix** — smallest diff to resolve.
4. **Phase 3: Prove** — run tests or checks and report results.
5. **Phase 4: Risk** — document production risk.

### Stop conditions
- If migration history is inconsistent or missing revisions: **stop** and propose a safe reset plan.
- If DB has tables but `alembic_version` is missing: **stop** and propose options.

## Deployment & Hosting

### Cloudflare (DNS/routing)
- `@` A record → `76.76.21.21` (Vercel edge), proxied.
- `app` CNAME → `<vercel-deployment>.vercel.app`, proxied.
- `www` CNAME → `f4a7529fdd483210.vercel-dns-017.com`, proxied; redirect `www` → `https://app.libertyplacehoa.com/$1`.
- `api` CNAME → `libertyplacehoa.onrender.com`, **DNS-only** (Render TLS requires no proxy).
- Redirect rule must avoid double protocol (`https://https://...`).

### Vercel (frontend)
- Project root: `frontend/`.
- Build command: `npm run build`.
- Output: `frontend/dist`.
- SPA routing via `frontend/vercel.json` rewrite `/(.*)` → `/index.html`.
- `VITE_API_URL` must match `https://api.libertyplacehoa.com`.
- After repo renames, verify Vercel points at the current repo.

### Render (backend)
- Service name: `hoa-backend` (region: Oregon, `gcp-us-west1`).
- Build: `pip install -r requirements.txt`.
- Start: `python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- Required env vars:
  - `DATABASE_URL` (managed Postgres).
  - `FRONTEND_URL=https://app.libertyplacehoa.com`.
  - `API_BASE=https://api.libertyplacehoa.com`.
  - `ADDITIONAL_TRUSTED_HOSTS=libertyplacehoa.onrender.com,api.libertyplacehoa.com`.
  - Email (Google Workspace SMTP):
    - `EMAIL_BACKEND=smtp`
    - `SMTP_HOST=smtp.gmail.com`
    - `SMTP_PORT=587`
    - `SMTP_USERNAME=<workspace user>`
    - `SMTP_PASSWORD=<app password>`
    - `SMTP_USE_TLS=true`
    - `EMAIL_FROM=admin@libertyplacehoa.com`
  - Storage: `FILE_STORAGE_BACKEND=local` (Cloudflare serves `/uploads`).
- Cold start: Render free tier sleeps after ~15 minutes; first request can take up to a minute.
- Health endpoint: `/health`.
- Runtime diagnostics: `/system/runtime` (SYSADMIN only) returns sanitized runtime config for debugging env drift.
- CI runs Alembic before pytest to ensure `audit_logs` exists.

## Platform Consolidation Options

### Current provider footprint
- Render for backend hosting + migrations.
- Vercel for frontend hosting.
- Cloudflare for DNS/routing.
- Google Workspace for SMTP (`smtp.gmail.com`).
- Possible Postgres provider: Neon-style connection strings are referenced in config.

### Option A — Keep Vercel + Render + DB provider, simplify Cloudflare
- **Pros:** minimal change, preserves frontend/backend separation.
- **Cons:** multi-vendor coordination remains.
- **Required changes:** DNS rules only; align `FRONTEND_URL`, `API_BASE`, and `ADDITIONAL_TRUSTED_HOSTS` to canonical domains.
- **Risk:** Low.
- **Next steps:** inventory DNS records; confirm canonical domains; validate `/health` and core flows after DNS changes.

### Option B — Move more to Cloudflare (Pages/Workers)
- **Pros:** fewer vendors, unified DNS + edge config.
- **Cons:** new frontend deployment path; edge limitations.
- **Required changes:** migrate frontend to Cloudflare Pages; validate rewrites and API base; update DNS/env.
- **Risk:** Medium.
- **Next steps:** prototype Pages deployment; verify SPA routing/API base; plan cutover and rollback.

### Option C — Single-vendor consolidation
- **Pros:** simpler billing/credentials; reduced config drift.
- **Cons:** largest change, highest risk.
- **Required changes:** migrate frontend + backend + DB to a single vendor; update DNS, auth callbacks, webhooks.
- **Risk:** High.
- **Next steps:** identify candidate vendor; prove staging end-to-end; execute phased migration with rollback.

## Project Reset & Local Setup

### Minimum local backend setup
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

### Minimum local frontend setup
```bash
cd frontend
npm install
npm run dev
```

### One-step local launch
```bash
python3 scripts/start_dev.py
```

### Minimum deployed/healthy path
1. Start command must remain:
   ```bash
   python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```
2. Frontend deploys from `frontend/` via `frontend/vercel.json`.
3. DNS routing must follow Cloudflare rules (especially `api` DNS-only).
4. `/health` should return success after migrations.

### Stabilization priorities (“stop the bleeding”)
1. Build/compile: backend deps, frontend build, CI steps.
2. Migration safety: bootstrap succeeds and DB is at Alembic head.
3. Environment drift: reconcile `.env.template`, Render env, and frontend env.
4. Deploy parity: local behavior matches Render + Vercel (URLs, CORS, API base).

### Known unknowns checklist
- Confirm production DB provider and connection string format.
- Confirm which email backend is active in production.
- Verify `FRONTEND_URL`, `API_BASE`, and `ADDITIONAL_TRUSTED_HOSTS` values in production.
- Confirm canonical domain routing (Cloudflare rules + cert expectations).
- Identify where secrets are stored (Render dashboard, Vercel secrets, etc.).
- Confirm health check endpoints used by monitoring.
- Verify whether any background jobs beyond `scripts/run_autopay.py` exist.

## Launch Readiness Checklist

### Stage 0 — Repo compiles/builds
**DoD**
- Backend dependencies install without errors.
- Frontend dependencies install without errors.
- Lint/test steps complete or are explicitly waived.

**Checklist**
- `pip install -r requirements.txt`
- `cd frontend && npm install`
- (Optional) `pytest` or existing CI checks

### Stage 1 — Local run (frontend + backend) with sample env
**DoD**
- Backend starts locally and serves `/health`.
- Frontend starts locally and can reach the backend API.
- `.env.template` values are copied into working `.env` files.

**Checklist**
- `cp .env.template .env`
- `cp frontend/.env.template frontend/.env` (if needed)
- `alembic upgrade head`
- `uvicorn backend.main:app --reload --port 8000`
- `cd frontend && npm run dev`

### Stage 2 — DB migrations safe and repeatable (Render bootstrap path)
**DoD**
- Render startup path succeeds: `python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- New DB boots cleanly with Alembic head.
- No manual intervention needed to start the service.

**Checklist**
- `python scripts/bootstrap_migrations.py reconcile`
- Confirm Alembic head matches `backend/migrations`.

### Stage 3 — Deployed smoke tests + health endpoints
**DoD**
- Backend `/health` returns 200 on deployed domain.
- Frontend loads and can authenticate (if enabled).
- CORS configured for deployed frontend URL.

**Checklist**
- GET `https://<backend-domain>/health`
- Load `https://<frontend-domain>`
- Confirm login and a basic API call

### Stage 4 — Email integration test plan (Google Workspace)
**DoD**
- SMTP test plan documented and verified against a test inbox.
- Email backend configuration confirmed in deployment environment.

**Checklist**
- Configure SMTP credentials in environment
- Send a test email via the API or admin action
- Validate SPF/DKIM alignment (if applicable)

### Stage 5 — Observability + error reporting
**DoD**
- Monitoring/alerting endpoints defined.
- Error logs are accessible and actionable.
- Ownership for alerts and on-call response is documented.

**Checklist**
- Identify existing logging/monitoring provider (placeholder if unknown)
- Define alert thresholds for `/health` failures
- Confirm log access for backend and frontend deployments

## Phase 1 Scope

### Delivered
- RBAC foundations with roles HOMEOWNER, BOARD, TREASURER, SECRETARY, ARC, AUDITOR, ATTORNEY, SYSADMIN and middleware helpers (`require_roles`, `require_minimum_role`).
- JWT login, SYSADMIN-restricted registration, `/auth/me`, bcrypt password hashing.
- Audit logging helper for sensitive create/update actions (before/after snapshots).
- Homeowner directory CRUD with self-service update requests and approval workflow.
- Billing & ledger models, late fee utility, CSV-friendly ledger helper, summary metrics endpoint.
- Communications endpoint (delivery logging, stub email sending, PDF placeholder for print packets).
- Vendor contracts CRUD with renewal metadata.
- Frontend portal: login, dashboard, billing views, contracts list (board-only), owner directory (board-only), homeowner profile change requests, communications creation UI.
- Developer tooling: initial migration, role seeding at startup, SYSADMIN creation script.

### Deferred
- Real email/PDF generation and address label exports (stubs in place).
- Payment processor integration and homeowner self-service payment submission with validation.
- Advanced reporting, QuickBooks export automation, Postgres production hardening.
- Two-factor authentication and persistent sessions.
- Automated test coverage and CI/CD pipeline.

## Phase 4 (Polish & Ops) Checklist

### Deploy & DNS sanity
- Frontend: ensure SPA rewrite `/(.*)` → `/index.html`; `VITE_API_URL=https://api.libertyplacehoa.com`.
- Backend: start command uses `python scripts/bootstrap_migrations.py reconcile` then `uvicorn backend.main:app`.
- Cloudflare: `api.libertyplacehoa.com` DNS-only; `app`/`www` proxied; redirect `www` → `https://app.libertyplacehoa.com/$1` without double `https://`.

### Environment keys (prod)
- API: `FRONTEND_URL`, `API_BASE`, `DATABASE_URL`, `EMAIL_BACKEND=smtp`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS=true`.
- Storage: `FILE_STORAGE_BACKEND` (`local` or `s3`), `UPLOADS_PUBLIC_URL` if proxied.
- CORS: `ADDITIONAL_CORS_ORIGINS` for temporary admin hosts.

### Monitoring & diagnostics
- `/health` for uptime checks; `/system/runtime` (SYSADMIN) for env drift checks.
- Logs are structured JSON via pythonjsonlogger when installed; otherwise plain text.
- Optional: external ping every 10 minutes to keep Render warm.

### Performance & bundles
- Run Lighthouse (desktop/mobile) against `app.libertyplacehoa.com` and resolve contrast/tap-target/bundle issues.
- For large lists (Owners/Violations/ARC), enable server pagination or virtualized rows if sluggish; table component supports pagination props.
- WebSocket keepalive enabled for notifications; ensure Cloudflare allows `wss` to `api.` host.

### Accessibility
- Verify skip links, heading order, ARIA labels on forms, focus outlines (axe or Lighthouse).

### Tests & lint
- Backend: `. .venv/bin/activate && pytest tests/test_elections.py tests/test_audit_logs.py` (extend to full suite later).
- Frontend: `cd frontend && npm run lint`.

### Release steps (manual)
```bash
git status
git add .
git commit -m "Phase 4 polish: docs + websocket keepalive + utc timestamps"
git push origin <branch>
```

## Admin Workflow Map

This section documents current workflows and behaviors visible in the running application. If a detail is unclear, it is explicitly noted as **“Current behavior unclear / needs confirmation.”**

### Account

**Purpose**
Provide login, profile management, password changes, and two-factor authentication (2FA) for users. Also governs how new user accounts and roles are created by admins.

**Primary Actors**
- Homeowner
- Board / Treasurer / Secretary
- SYSADMIN
- System (authentication services)

**Key States / Statuses**
- **User.is_active**: active vs. archived/inactive (archived users cannot log in).
- **Two-factor**: enabled vs. disabled.
- **Roles**: each user has one or more roles and a designated primary role.

**Triggers**
- User login or refresh token request.
- User self-service profile update.
- Password change request.
- 2FA setup, enable, or disable actions.
- SYSADMIN registers a new user or updates roles.

**Workflow Steps**
1. **Login**
   - User submits email + password.
   - If credentials are valid and user is active, system checks whether 2FA is enabled.
   - If 2FA is enabled, user must supply a valid OTP code.
   - Successful login returns access + refresh tokens.
2. **Refresh token**
   - User submits a refresh token.
   - System validates token type, user identity, and active status.
   - New access + refresh tokens are returned.
3. **Self-service profile update**
   - User submits changes to name and/or email.
   - If changing email, the current password is required.
   - System updates the record and logs the change.
4. **Password change**
   - User submits current and new password.
   - System validates current password and updates stored hash.
5. **2FA setup and enable**
   - User requests a 2FA setup secret (QR/OTP URI returned).
   - User enables 2FA by confirming a valid OTP code.
   - User can later disable 2FA with a valid OTP code.
6. **Admin user registration**
   - SYSADMIN creates a user with selected roles.
   - Roles are validated and assigned; highest-priority role becomes the primary role.
   - If the new user is a homeowner, the system ensures they are linked to an Owner record (creating a placeholder Owner if needed).
7. **Role updates**
   - SYSADMIN updates role assignments.
   - System ensures at least one active SYSADMIN remains.

**Side Effects**
- Audit log entries for user creation, role updates, profile updates, and password changes.
- Homeowner users are automatically linked to an Owner record when created or updated.

**Permissions / Access Control**
- **Login / refresh / 2FA / self-service**: any authenticated user.
- **Register new users & update roles**: SYSADMIN only.
- **List users**: Board, Treasurer, Secretary, or SYSADMIN.

**Failure / Edge Cases**
- Invalid credentials or OTP codes block login.
- Email changes require the current password and unique email.
- Role updates are blocked if they would remove the last active SYSADMIN.
- Archived/inactive users cannot log in.

---

### ARC Requests

**Purpose**
Track architectural review requests submitted by homeowners and reviewed by ARC/Board members.

**Primary Actors**
- Homeowner (requester)
- ARC member / Board / Secretary / Treasurer / SYSADMIN (reviewers/managers)
- System (notifications)

**Key States / Statuses**
ARC request statuses:
- **DRAFT**: request created but not yet submitted.
- **SUBMITTED**: submitted for review.
- **IN_REVIEW**: under active review.
- **REVISION_REQUESTED**: applicant must revise and resubmit.
- **REVIEW_COMPLETE**: review finished; awaiting final transition.
- **PASSED / FAILED**: outcome from ARC vote threshold.
- **APPROVED / APPROVED_WITH_CONDITIONS / DENIED**: final decision states.
- **COMPLETED**: work completed.
- **ARCHIVED**: closed/archived.

ARC review decisions:
- **PASS** or **FAIL** (individual reviewer vote).

ARC condition status:
- **OPEN** or **RESOLVED**.

Inspection results:
- **PASSED / FAILED / N/A**.

**Triggers**
- Homeowner or staff creates an ARC request.
- Homeowner submits the request (DRAFT → SUBMITTED).
- Reviewers submit PASS/FAIL reviews.
- Reviewer or manager transitions status (e.g., IN_REVIEW → APPROVED).
- Reviewer adds conditions or inspections.
- System sends decision emails on PASS/FAIL if templates exist.

**Workflow Steps**
1. **Create request**
   - A draft request is created for an owner address.
   - Homeowners may only create requests for linked owner records.
2. **Submit request**
   - Homeowner submits a DRAFT request, moving it to SUBMITTED.
3. **Review phase**
   - ARC/Board reviewers submit PASS or FAIL decisions.
   - The system counts eligible reviewers and moves the request to PASSED or FAILED when a threshold is met.
   - Managers can also directly transition states within allowed status transitions.
4. **Decision notification**
   - When a request becomes PASSED or FAILED, the system attempts to email the applicant using ARC templates.
5. **Post-decision**
   - Managers can move requests into APPROVED, APPROVED_WITH_CONDITIONS, DENIED, COMPLETED, or ARCHIVED as appropriate.
6. **Reopen**
   - Closed requests (approved/denied/completed/archived, etc.) can be reopened as a new IN_REVIEW request with copied attachments and conditions.

**Side Effects**
- Audit logs for request creation, updates, status transitions, reviews, conditions, inspections, and reopen actions.
- Email notification on PASS/FAIL if templates are configured.

**Permissions / Access Control**
- **Homeowners**: can view and modify their own requests (while in DRAFT) and submit them.
- **ARC/Board/Secretary/Treasurer/SYSADMIN**: can view, update, review, add conditions/inspections, and transition statuses.

**Failure / Edge Cases**
- Invalid status transitions are rejected.
- Homeowners cannot submit for unlinked addresses.
- Decision notifications are skipped if no recipient email or missing templates.

---

### Billing

**Purpose**
Manage homeowner invoices, payments, late fees, billing policy, and overdue escalations.

**Primary Actors**
- Homeowner
- Board / Treasurer / SYSADMIN
- Auditor (read-only access to some reports)
- System (late fee automation, autopay jobs)

**Key States / Statuses**
Invoices:
- **OPEN** (default)
- **PAID** (set when fully paid via Stripe or autopay)
- **VOID** is referenced for validations, but no explicit void workflow is defined (current behavior unclear / needs confirmation).

Autopay enrollment:
- **PENDING** (initial enrollment)
- **CANCELLED**
- Provider status fields may include **PENDING_PROVIDER**, **CANCELLED**, or other provider statuses.

Vendor payments:
- **PENDING** → **SUBMITTED** → **PAID** (with **FAILED** allowed for retries).

Late fees:
- Late fee tiers define triggers by days past grace period.

**Triggers**
- Admin creates or updates invoices.
- Homeowner or staff records payments.
- Manual late fee application.
- System auto-applies late fees when listing invoices or summaries.
- Autopay job runs daily (Render cron) to pay eligible invoices.
- Overdue notice or attorney escalation actions.

**Workflow Steps**
1. **Invoice creation**
   - Staff creates an invoice for an owner (must be active/not archived).
   - The invoice is recorded in the ledger.
2. **Payment recording**
   - Homeowner or staff records a payment (manual) OR Stripe webhook records a payment.
   - Ledger is updated; invoice may move to PAID if fully covered.
3. **Late fees**
   - Billing policy defines grace period and late fee tiers.
   - Late fees are automatically applied when invoice lists or summaries are requested.
   - Staff can also apply a manual late fee.
4. **Autopay**
   - Homeowner (or staff) sets up autopay enrollment.
   - Daily autopay job checks OPEN invoices older than 30 days and issues autopay payments.
5. **Overdue escalation**
   - Staff can contact overdue owners via in-app notifications.
   - Staff can generate an attorney packet (PDF) and notify attorney role.
6. **Vendor payments**
   - Staff create vendor payments (optionally tied to contracts).
   - Payments move from PENDING → SUBMITTED → PAID.

**Side Effects**
- Audit log entries for invoice creation/updates, payment recording, late fee application, policy updates, autopay changes, and vendor payment updates.
- Ledger entries are created for invoices, payments, and adjustments.
- Overdue contact creates notifications for homeowners.
- Attorney escalation creates a PDF and notifies the ATTORNEY role.

**Permissions / Access Control**
- **Homeowners**: view their own invoices/ledger; record payments for their own account; manage autopay.
- **Board/Treasurer/SYSADMIN**: full billing management, policies, and vendor payments.
- **Auditor**: can view invoices and billing summaries.

**Failure / Edge Cases**
- Archived owners cannot receive invoices or payments.
- Stripe payments are skipped if invoice is already paid or void.
- Autopay only runs for active enrollments and invoices older than 30 days.
- Billing policy updates replace tiers not included in the update.

---

### Documents

**Purpose**
Maintain a governance document library with folders and downloadable files.

**Primary Actors**
- Board / Treasurer / Secretary / SYSADMIN (managers)
- Homeowners (view/download)

**Key States / Statuses**
- No explicit status fields for folders or documents.

**Triggers**
- Manager creates/updates/deletes folders.
- Manager uploads or deletes documents.
- Any logged-in user downloads a document.

**Workflow Steps**
1. **Folder management**
   - Managers create, rename, or delete folders.
   - On folder deletion, child folders and documents are moved up to the parent.
2. **Document upload**
   - Manager uploads a file and assigns it to a folder (or leave uncategorized).
3. **Document download**
   - Any authenticated user can download documents.

**Side Effects**
- Files are stored in the configured storage backend.
- No explicit audit logs in the document routes (current behavior unclear / needs confirmation).

**Permissions / Access Control**
- **Manage folders/documents**: Board, Treasurer, Secretary, SYSADMIN.
- **View/download**: any authenticated user.

**Failure / Edge Cases**
- Upload fails if file is empty.
- Download fails if document not found.

---

### Elections

**Purpose**
Run community elections with candidate lists, ballots, and vote tallying.

**Primary Actors**
- Board / Secretary / SYSADMIN (election managers)
- Homeowners (voters)
- System (notifications)

**Key States / Statuses**
Election status values observed:
- **DRAFT**
- **SCHEDULED**
- **OPEN**
- **CLOSED**
- **ARCHIVED**

Ballot status fields:
- **issued_at** (issued)
- **voted_at** (used)
- **invalidated_at** (invalidated)

**Triggers**
- Manager creates/updates elections.
- Manager adds/removes candidates.
- Manager generates ballots (tokens) for owners.
- Homeowner votes via authenticated portal or token link.
- Manager updates election status (OPEN/CLOSED/etc.).

**Workflow Steps**
1. **Create election**
   - Manager creates a new election (default DRAFT unless specified).
2. **Manage candidates**
   - Manager adds or removes candidates.
3. **Issue ballots**
   - Manager generates ballots; tokens are created for each active owner.
4. **Open voting**
   - Manager updates status to OPEN; homeowners can vote.
   - System can notify homeowners when an election opens.
5. **Voting**
   - Homeowners vote via authenticated portal or public token link.
   - Each ballot can be used once; a vote records the selection or write-in.
6. **Close election**
   - Manager changes status to CLOSED; results are available to managers.
7. **Results and reports**
   - Results can be viewed in-app or exported as CSV.

**Side Effects**
- Notifications sent when election status changes (OPEN/SCHEDULED/CLOSED).
- Voting records stored for tallying and reporting.

**Permissions / Access Control**
- **Manage elections/candidates/ballots**: Board, Secretary, SYSADMIN.
- **Vote**: authenticated homeowners for OPEN elections; token links for public voting.
- **Results and stats**: manager roles only.

**Failure / Edge Cases**
- Voting is blocked if election is not OPEN.
- Ballots cannot be reused or used after invalidation.
- Candidate ID must belong to the election.

---

### Meetings

**Purpose**
Schedule HOA meetings and publish minutes.

**Primary Actors**
- Board / Treasurer / Secretary / SYSADMIN (managers)
- Homeowners (viewers)

**Key States / Statuses**
- No explicit status field; meetings are determined by date/time.

**Triggers**
- Manager creates or updates meeting details.
- Manager uploads meeting minutes.
- Users list or download minutes.

**Workflow Steps**
1. **Create meeting**
   - Manager creates a meeting with date/time/location/Zoom link.
2. **Update meeting**
   - Manager edits meeting details as needed.
3. **Upload minutes**
   - After the meeting, manager uploads minutes; download link becomes available.

**Side Effects**
- Uploaded minutes are stored in the configured file storage.
- No explicit audit logs in the meeting routes (current behavior unclear / needs confirmation).

**Permissions / Access Control**
- **Create/update/delete meetings or upload minutes**: Board, Treasurer, Secretary, SYSADMIN.
- **View meetings and download minutes**: any authenticated user.

**Failure / Edge Cases**
- Minutes upload fails if file is empty.
- Download fails if minutes file is missing.

---

### Violations

**Purpose**
Track covenant violations, notices, fines, hearings, and appeals.

**Primary Actors**
- Board / Secretary / SYSADMIN (managers)
- Treasurer / Attorney (view and notification recipients)
- Homeowners (view/respond)
- System (notices, notifications, invoices)

**Key States / Statuses**
Violation status values:
- **NEW**
- **UNDER_REVIEW**
- **WARNING_SENT**
- **HEARING**
- **FINE_ACTIVE**
- **RESOLVED**
- **ARCHIVED**

Appeal status values:
- **PENDING** (default)
- Decision values are stored as free-text status when decided.

**Triggers**
- Manager creates a violation.
- Manager transitions a violation status.
- Manager issues additional fines.
- Homeowner submits an appeal.
- Board decides an appeal.

**Workflow Steps**
1. **Create violation**
   - Manager creates a violation for an owner (or a user, which can create a placeholder owner).
2. **Status transitions**
   - Violations move through allowed transitions (e.g., NEW → UNDER_REVIEW → WARNING_SENT → HEARING → FINE_ACTIVE → RESOLVED → ARCHIVED).
   - Each transition can generate notices or fines depending on the new status.
3. **Notices and fines**
   - WARNING_SENT, HEARING, and FINE_ACTIVE trigger templated notices and a PDF notice file.
   - FINE_ACTIVE creates a payable invoice; additional fines can be added while in FINE_ACTIVE.
4. **Appeals**
   - Homeowners can submit appeals.
   - Board reviews and records a decision.
5. **Messages**
   - Both managers and homeowners can post messages on a violation thread.

**Side Effects**
- Audit logs for creation, updates, status transitions, messages, appeals, and fines.
- Notifications to homeowners and managers on status changes.
- Violation notices generate PDFs and emails (if homeowner email exists).
- Fines create invoices and ledger entries.

**Permissions / Access Control**
- **Create/update/transition**: Board, Secretary, SYSADMIN.
- **View**: managers can view all; homeowners only their own.
- **Appeals**: homeowners for their own violations; Board decides.
- **Messages**: homeowners can message their own violations; managers can message all.

**Failure / Edge Cases**
- Invalid status transitions are blocked.
- FINE_ACTIVE requires a fine amount.
- Notices are skipped if required data (e.g., email) is missing.
- Appeals can only be submitted for the homeowner’s own violation.

---

### Announcements

**Purpose**
Send community announcements and broadcast messages to owners via email or printed packets.

**Primary Actors**
- Board / Secretary / SYSADMIN
- System (email and PDF generation)

**Key States / Statuses**
- No explicit status field for announcements or messages.

**Triggers**
- Admin creates an announcement, broadcast, or communication message.

**Workflow Steps**
1. **Announcements**
   - Admin selects delivery methods (email, print).
   - System builds a recipient list and optionally generates a PDF packet.
   - Email deliveries are queued in a background task.
2. **Broadcast messages**
   - Admin chooses a segment (all owners, delinquent owners, rental owners).
   - System builds recipient list for the segment.
   - Broadcast record is created (email delivery only).
3. **Communication messages**
   - Admin sends a broadcast (segment-based) or general announcement (delivery methods).

**Side Effects**
- Audit logs for announcement, broadcast, and communication message creation.
- Optional PDF packet generation for print delivery.
- Emails are sent asynchronously.

**Permissions / Access Control**
- **Create/list announcements, broadcasts, and messages**: Board, Secretary, SYSADMIN.

**Failure / Edge Cases**
- Empty subject/body is rejected.
- Broadcasts fail if no recipients have emails for the selected segment.

---

### Budget

**Purpose**
Plan and approve the annual HOA budget, including reserve planning and attachments.

**Primary Actors**
- Board / Treasurer / SYSADMIN (managers)
- Homeowners (view approved budgets)
- System (notifications)

**Key States / Statuses**
Budget status values:
- **DRAFT** (default)
- **APPROVED** (locked)

**Triggers**
- Create/update budget and line items.
- Board approvals.
- Manual lock/unlock actions.

**Workflow Steps**
1. **Draft budget**
   - Managers create a budget or update draft details.
2. **Line items & reserves**
   - Managers add/edit/delete budget line items and reserve plan items.
3. **Approvals**
   - Board members approve the budget.
   - When required approval count is reached, budget auto-locks and becomes APPROVED.
4. **Lock/Unlock**
   - Managers can manually lock a budget if required approvals are satisfied.
   - SYSADMIN can unlock an approved budget (returns to DRAFT and clears approvals).

**Side Effects**
- Audit logs for budget creation, updates, line items, approvals, lock/unlock, and attachments.
- Notifications sent to homeowners when a budget is approved.

**Permissions / Access Control**
- **Create/update/approve**: Board, Treasurer, SYSADMIN.
- **Unlock approved budget**: SYSADMIN only.
- **View**: homeowners can view approved budgets; managers can view drafts.

**Failure / Edge Cases**
- Budgets cannot be locked without line items.
- Approved budgets cannot be edited except by SYSADMIN unlock.

---

### Contracts

**Purpose**
Store vendor contracts, including attachments and renewal metadata.

**Primary Actors**
- Treasurer / SYSADMIN (editors)
- Board / Secretary / Attorney / Auditor / Legal (viewers)

**Key States / Statuses**
- No explicit status field for contracts.

**Triggers**
- Create/update contracts.
- Upload/download contract attachments.

**Workflow Steps**
1. **Create contract**
   - Treasurer or SYSADMIN adds contract details.
2. **Update contract**
   - Editors modify contract data (dates, renewal options, etc.).
3. **Attach files**
   - Editors upload a PDF attachment; old files are replaced.

**Side Effects**
- Audit logs for contract creation and updates.
- Files stored in storage backend.

**Permissions / Access Control**
- **Create/update/attach**: Treasurer, SYSADMIN.
- **View**: Board, Treasurer, Secretary, SYSADMIN, Attorney, Auditor, Legal.

**Failure / Edge Cases**
- Attachments must be PDFs; empty file uploads are rejected.

---

### Legal

**Purpose**
Send formal legal communications to contract contacts using legal templates.

**Primary Actors**
- Legal role users
- SYSADMIN
- System (email dispatch)

**Key States / Statuses**
- No explicit status field for legal messages.

**Triggers**
- Legal/SYSADMIN sends a legal message tied to a contract.

**Workflow Steps**
1. **Choose template and contract**
   - Legal user chooses a template and contract contact.
2. **Send message**
   - System dispatches the email using the legal sender address.

**Side Effects**
- Audit log entry for each legal message sent.

**Permissions / Access Control**
- **View legal templates & send messages**: Legal role or SYSADMIN.

**Failure / Edge Cases**
- Contract must have a contact email.
- Subject/body cannot be empty.

---

### Owners

**Purpose**
Maintain owner records and link them to user accounts.

**Primary Actors**
- Board / Treasurer / Secretary / SYSADMIN
- Homeowners (self-service updates)
- System (USPS welcome notice creation)

**Key States / Statuses**
Owner archival status:
- **is_archived = false** (active)
- **is_archived = true** (archived)

Owner update request status:
- **PENDING**
- **APPROVED**
- **REJECTED**

**Triggers**
- Create/update owner records.
- Homeowner submits update request (proposal).
- Board reviews and approves/rejects proposals.
- SYSADMIN archives or restores owners.
- SYSADMIN links/unlinks users to owners.

**Workflow Steps**
1. **Owner creation**
   - Board/Treasurer/SYSADMIN creates an owner record.
   - System attempts to create a USPS welcome notice for the new owner.
2. **Owner update requests**
   - Homeowner proposes updates; request remains PENDING.
   - Board/Secretary/SYSADMIN approves (changes applied) or rejects.
3. **Archive/restore**
   - SYSADMIN archives an owner (lot renamed with ARCHIVED suffix and linked users deactivated).
   - SYSADMIN restores an owner (lot restored if no conflict; optional user reactivation).
4. **Link/unlink users**
   - SYSADMIN links a user to an owner (homeowners may only link to one active property).

**Side Effects**
- Audit logs for owner creation, updates, proposals, archive/restore, and user link/unlink.
- Archiving deactivates linked user accounts.
- USPS welcome notice creation can create a Notice and Paperwork item.

**Permissions / Access Control**
- **Create/update owners**: Board, Treasurer, Secretary, SYSADMIN.
- **Archive/restore, link/unlink users**: SYSADMIN only.
- **Propose updates**: homeowner for their record; Board/Secretary/SYSADMIN for any record.
- **View**: managers can view all; homeowners only their own.

**Failure / Edge Cases**
- Archived owners cannot receive invoices or new ARC/violation filings.
- Restore fails if another active owner already uses the original lot.

---

### Reconciliation

**Purpose**
Import bank statements and match transactions to payments/invoices.

**Primary Actors**
- Board / Treasurer / SYSADMIN
- System (automatic matching)

**Key States / Statuses**
Bank transaction status values:
- **PENDING** (imported)
- **MATCHED**
- **UNMATCHED**

**Triggers**
- Upload bank statement CSV.
- Review transactions and reconciliations.

**Workflow Steps**
1. **Import statement**
   - Admin uploads a CSV statement.
   - System parses transactions and stores them.
2. **Automatic matching**
   - System attempts to match transactions to payments (priority) or invoices (fallback) by amount and date proximity.
3. **Review**
   - Admin views reconciliations and transactions, filtered by status as needed.

**Side Effects**
- Audit logs for imports and reconciliation views.
- Stored copy of the uploaded statement in file storage.

**Permissions / Access Control**
- **Import and view**: Board, Treasurer, SYSADMIN.

**Failure / Edge Cases**
- CSV must include date, description, and amount headers.
- Invalid CSV format rejects import.
- Matching is best-effort; unmatched transactions remain for manual review.

---

### Reports

**Purpose**
Generate financial and compliance CSV reports.

**Primary Actors**
- Board / SYSADMIN

**Key States / Statuses**
- No explicit report status; reports are generated on demand.

**Triggers**
- Admin requests report exports or data endpoints.

**Workflow Steps**
1. **Generate report**
   - System aggregates report data and returns CSV.
2. **Audit access**
   - Each report request logs an audit entry.

**Side Effects**
- Audit log entries for each report access.

**Permissions / Access Control**
- **Export reports**: Board, SYSADMIN.

**Failure / Edge Cases**
- Current behavior unclear / needs confirmation for report timeouts or large data sets.

---

### USPS

**Purpose**
Create and manage postal notices, including USPS welcome packets and paper mail dispatch workflows.

**Primary Actors**
- Board / Treasurer / Secretary / SYSADMIN
- System (notice creation, PDF generation)
- External mail providers (Click2Mail, Certified Mail)

**Key States / Statuses**
Notice status values:
- **PENDING**
- **SENT_EMAIL**
- **IN_PAPERWORK**
- **MAILED**

Paperwork item status values:
- **PENDING**
- **CLAIMED**
- **MAILED**

**Triggers**
- Owner creation (creates USPS welcome notice).
- Board creates a notice manually.
- Board dispatches paper mail through Click2Mail or Certified Mail.

**Workflow Steps**
1. **Notice creation**
   - Admin creates a notice (or system creates a USPS welcome notice).
   - Delivery channel is resolved based on notice type and owner preferences.
2. **Email delivery**
   - If email delivery is allowed, the notice is emailed and marked SENT_EMAIL.
3. **Paperwork queue**
   - If paper delivery is required, a Paperwork item is created and linked to the notice.
4. **Claim and dispatch**
   - Board member can claim a paperwork item.
   - Item can be manually marked MAILED or dispatched via Click2Mail/Certified Mail.

**Side Effects**
- Audit log entry for notice creation and certified-mail dispatch.
- PDF notice generated and stored.
- Provider status, tracking numbers, and delivery metadata stored when dispatched.

**Permissions / Access Control**
- **Create notices and manage paperwork**: Board, Treasurer, Secretary, SYSADMIN.
- **View paperwork**: Board roles.

**Failure / Edge Cases**
- Click2Mail or Certified Mail dispatch fails if not configured.
- Paperwork PDFs can be regenerated if missing, but dispatch fails if generation fails.

---

### Admin

**Purpose**
Provide sysadmin tooling such as user provisioning, login background management, and runtime diagnostics.

**Primary Actors**
- SYSADMIN

**Key States / Statuses**
- No explicit status fields; admin actions affect system configuration and user roles.

**Triggers**
- SYSADMIN uploads a login background image.
- SYSADMIN requests runtime diagnostics.
- SYSADMIN sends test email (requires admin token).

**Workflow Steps**
1. **Login background**
   - SYSADMIN uploads a PNG/JPG.
   - System stores and returns the URL.
2. **Runtime diagnostics**
   - SYSADMIN requests configuration details (non-sensitive settings only).
3. **Test email**
   - SYSADMIN submits recipient + message with admin token.
   - System sends a test email using configured email backend.

**Side Effects**
- Stored background image in file storage.
- Test email sent if admin token and backend are configured.

**Permissions / Access Control**
- **All admin endpoints**: SYSADMIN only.

**Failure / Edge Cases**
- Invalid file type for background image is rejected.
- Test email endpoint is disabled if no admin token is configured.

---

### Audit Log

**Purpose**
Provide a tamper-resistant history of system changes and admin actions.

**Primary Actors**
- SYSADMIN
- Auditor
- System (automatic audit middleware)

**Key States / Statuses**
- No explicit status; each entry is immutable.

**Triggers**
- Any mutating API request (POST/PUT/PATCH/DELETE) is logged automatically.
- Services explicitly call audit logging for significant actions.

**Workflow Steps**
1. **Automatic logging**
   - Middleware records HTTP write actions (excluding the notifications WebSocket).
2. **Explicit logging**
   - Services and APIs add audit entries for key business actions.
3. **Review**
   - SYSADMIN or Auditor can list audit logs.

**Side Effects**
- Audit logs stored with before/after snapshots when provided.

**Permissions / Access Control**
- **View audit logs**: SYSADMIN or Auditor.

**Failure / Edge Cases**
- Actor may be missing (system or unauthenticated actions); audit entries still recorded.

---

### Templates

**Purpose**
Manage reusable message templates for notices, legal messages, ARC decisions, billing, and announcements.

**Primary Actors**
- SYSADMIN

**Key States / Statuses**
- **is_archived = false** (active)
- **is_archived = true** (archived)

**Triggers**
- SYSADMIN creates, updates, or archives templates.
- SYSADMIN views template types or merge tags.

**Workflow Steps**
1. **Create template**
   - SYSADMIN selects a valid template type and defines subject/body.
2. **Update template**
   - SYSADMIN edits fields or archives the template.
3. **Use template**
   - Other workflows render templates with merge tags (e.g., ARC decision emails, violation notices, legal messages).

**Side Effects**
- Audit logs for template creation and updates.

**Permissions / Access Control**
- **All template actions**: SYSADMIN only.

**Failure / Edge Cases**
- Invalid template type codes are rejected.

---

## Future: Admin-Editable Workflows (Non-Implemented)

This section is conceptual only and reflects no current implementation.

- Admin-only Workflows UI to view module steps in a human-readable flow.
- Attach notification templates to steps (e.g., “Violation → Warning Sent”).
- Enable/disable or reorder steps to match local policy.
- No schema or API definitions are proposed here.
