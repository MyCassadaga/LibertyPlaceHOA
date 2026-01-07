# Architecture Map (Liberty Place HOA)

> Scope: This document summarizes runtime entrypoints, data layer setup, auth/admin flows, audit logging, and key invariants by reading the current codebase. No code changes are implied here.

## 1) Runtime entrypoints

### Render deployment
- **Render service config:** `render.yaml` defines a `hoa-backend` web service that installs dependencies with `pip install -r requirements.txt` and starts the API with a bash command that first runs the migration bootstrap script and then launches Uvicorn. The start command is:
  ```bash
  bash -lc "python scripts/bootstrap_migrations.py reconcile && uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
  ```
  This means Render will execute `scripts/bootstrap_migrations.py` before starting the FastAPI server on the Render-assigned `$PORT`. `DATABASE_URL` is injected from the `hoa-db` database resource, while `FRONTEND_URL`, `API_BASE`, and `ADDITIONAL_TRUSTED_HOSTS` are also set for runtime config. `APP_ENV` is set to `prod`.【F:render.yaml†L1-L40】
- **Background job:** `render.yaml` also defines a cron service (`hoa-autopay`) that runs `python scripts/run_autopay.py` daily at 06:00 UTC and shares the same database and environment variables as the web service.【F:render.yaml†L41-L70】

### Pre-uvicorn bootstrap
- **Script:** `scripts/bootstrap_migrations.py` is run before Uvicorn. It enforces that `DATABASE_URL` is present, validates it as a SQLAlchemy URL, and logs the target connection host/database. It inspects the database for existing tables, verifies Alembic revision state, and (depending on conditions) either stamps/upgrades the schema or refuses to run on an untracked existing schema. It ultimately runs `alembic upgrade head` for the configured `backend/alembic.ini` script location.【F:scripts/bootstrap_migrations.py†L1-L138】【F:scripts/bootstrap_migrations.py†L141-L190】

### Backend entrypoint + middleware chain
- **Entrypoint:** `backend/main.py` defines `app = FastAPI(...)` and is the Uvicorn entrypoint (`backend.main:app`). During startup (`lifespan`), it creates database tables (if missing), logs the Alembic revision, ensures seed roles/permissions, backfills user role links, ensures billing policy and notice types, generates contract renewal reminders, links homeowners to owners, and creates draft budgets for next year. It also configures a notification loop and attempts an SQLite backup on shutdown.【F:backend/main.py†L42-L138】【F:backend/main.py†L140-L213】
- **Middleware chain (configured in code order):**
  1. `TrustedHostMiddleware` uses `settings.trusted_hosts` to restrict host headers. 【F:backend/main.py†L140-L149】
  2. `CORSMiddleware` uses `settings.cors_allow_origins` plus an optional regex. 【F:backend/main.py†L150-L158】
  3. `SecurityHeadersMiddleware` adds basic security headers (HSTS, CSP, etc.). 【F:backend/main.py†L159-L162】【F:backend/core/security.py†L8-L38】
  4. Function middleware `request_context` assigns a request ID and adds it to responses. 【F:backend/main.py†L204-L210】
  5. Function middleware `audit_trail` logs write operations (`POST`, `PUT`, `PATCH`, `DELETE`) to the audit log, excluding `/notifications/ws`. 【F:backend/main.py†L234-L271】

## 2) Data layer

### SQLAlchemy models
- **Model definitions live in:** `backend/models/models.py`. This file contains the SQLAlchemy `Base` models (e.g., `User`, `Role`, `AuditLog`, `Owner`, etc.) and association tables like `user_roles` and `role_permissions`.【F:backend/models/models.py†L1-L188】

### Alembic configuration
- **Alembic config:** `backend/alembic.ini` sets the script location (`backend/migrations`) and provides a default SQLite URL (overridden at runtime).【F:backend/alembic.ini†L1-L20】
- **Migration environment:** `backend/migrations/env.py` loads `backend.config.settings` to populate `sqlalchemy.url`, imports models to register metadata, and uses `render_as_batch` when running against SQLite. It supports both offline and online migration modes.【F:backend/migrations/env.py†L1-L54】

### Migration graph overview
- **0001_baseline_baseline.py:** Base schema creation for the entire application, including users, roles, permissions, audit logs, owners, billing, contracts, notices, and other domain tables. (Large auto-generated migration.)【F:backend/migrations/versions/0001_baseline_baseline.py†L1-L174】
- **0002_make_audit_actor_nullable.py:** Alters `audit_logs.actor_user_id` to be nullable (allowing anonymous/system actions).【F:backend/migrations/versions/0002_make_audit_actor_nullable.py†L1-L30】
- **0003_seed_admin_user.py:** Seeds a `SYSADMIN` role (if missing), inserts an admin user (`admin@libertyplacehoa.com`) with a default password (`changeme`), and creates a `user_roles` link for that user. Uses PostgreSQL upserts to avoid duplicates.【F:backend/migrations/versions/0003_seed_admin_user.py†L1-L125】

## 3) Auth & admin

### Admin user creation/seed pathways
- **Manual CLI:** `backend/manage_create_admin.py` creates a `SYSADMIN` user with a provided email/password, ensuring default roles exist first. It assigns the primary `role_id` and also appends the `SYSADMIN` role in the `user_roles` association. This is intended as a one-off CLI command.【F:backend/manage_create_admin.py†L1-L72】
- **Migration seeding:** Alembic migration `0003_seed_admin_user.py` seeds a fixed admin (`admin@libertyplacehoa.com`) and `SYSADMIN` role if they do not exist, linking them in `user_roles`.【F:backend/migrations/versions/0003_seed_admin_user.py†L1-L125】
- **Seed script:** `scripts/seed_data.py` creates an example admin user (`admin@example.com`) with both `SYSADMIN` and `BOARD` roles for local development/testing. This script also uses `ensure_default_roles` and `ensure_user_role_links` from `backend/main.py`.【F:scripts/seed_data.py†L1-L99】
- **Bootstrap/runtime:** `backend/main.py` does **not** create admin users; it only ensures default roles, permissions, and data relationships during startup.【F:backend/main.py†L42-L213】

### JWT secret + required env vars
- **JWT secret loading:** `backend/config.py` loads `JWT_SECRET` (defaulting to `dev-secret-please-change`) and `JWT_ALGORITHM`. The auth module signs and validates JWTs with these settings. There is a warning if the default secret is used in production. 【F:backend/config.py†L17-L42】【F:backend/auth/jwt.py†L26-L52】【F:backend/core/security.py†L41-L49】
- **Environment requirements:**
  - `DATABASE_URL` is **required** at runtime for the Render bootstrap step; `scripts/bootstrap_migrations.py` exits if missing. 【F:scripts/bootstrap_migrations.py†L52-L78】
  - `JWT_SECRET` is strongly recommended (insecure default otherwise). 【F:backend/config.py†L17-L42】【F:backend/core/security.py†L41-L49】
  - Render sets `FRONTEND_URL`, `API_BASE`, and `ADDITIONAL_TRUSTED_HOSTS`, which drive CORS + trusted host config. 【F:render.yaml†L12-L32】【F:backend/config.py†L8-L113】

## 4) Audit logging

- **Write location:** Audit logs are persisted to the `audit_logs` table via `backend/services/audit.py`. Each entry includes timestamp, actor ID (nullable), action, target entity details, and serialized `before`/`after` payloads. 【F:backend/services/audit.py†L1-L36】【F:backend/models/models.py†L140-L165】
- **Automatic HTTP logging:** The `audit_trail` middleware in `backend/main.py` runs for mutating HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) and records the action as `{METHOD} {path}` with response status. WebSocket notifications (`/notifications/ws`) are excluded. 【F:backend/main.py†L234-L271】
- **Actor derivation:** `audit_trail` extracts a bearer token, decodes it, checks token type (`access` or unset), converts `sub` to an integer user ID, and verifies the user exists in the database. If validation fails or no token is present, `actor_user_id` remains `None`. 【F:backend/main.py†L244-L267】【F:backend/auth/jwt.py†L43-L74】
- **System vs anonymous assumptions:** The `audit_logs.actor_user_id` column is nullable, so the code explicitly allows audit entries without a user (e.g., anonymous requests, system-initiated operations). There is no hardcoded “system user”; missing/invalid tokens yield `actor_user_id = None`.【F:backend/models/models.py†L146-L165】【F:backend/migrations/versions/0002_make_audit_actor_nullable.py†L1-L30】【F:backend/main.py†L244-L271】

## 5) Invariants (most important)

1. **[schema]** `roles.name` is unique and non-null, and is the primary lookup for role checks (e.g., `SYSADMIN`).【F:backend/models/models.py†L35-L60】
2. **[schema]** `permissions.name` is unique and non-null. 【F:backend/models/models.py†L63-L71】
3. **[schema]** `users.email` is unique and non-null; used as the main identifier in admin creation and login. 【F:backend/models/models.py†L74-L88】
4. **[schema]** `users.role_id` is non-null and references a valid `roles.id` (primary role). 【F:backend/models/models.py†L80-L87】
5. **[schema]** `user_roles.assigned_at` is non-null; role assignments require a timestamp. 【F:backend/models/models.py†L27-L43】
6. **[data]** Default roles must exist (`DEFAULT_ROLES`), and startup/seed scripts attempt to enforce them. 【F:backend/constants.py†L1-L12】【F:backend/main.py†L163-L186】
7. **[data]** Users should have at least one role; `ensure_user_role_links` backfills `user.roles` from the primary role if missing. 【F:backend/main.py†L188-L213】
8. **[schema]** `audit_logs.actor_user_id` is nullable; audit entries may be anonymous/system. 【F:backend/models/models.py†L146-L165】【F:backend/migrations/versions/0002_make_audit_actor_nullable.py†L1-L30】
9. **[runtime]** Mutating HTTP requests (POST/PUT/PATCH/DELETE) are audited unless path starts with `/notifications/ws`. 【F:backend/main.py†L234-L271】
10. **[security]** JWTs must include a valid `sub` user ID and token type `access`/unset; otherwise requests are unauthorized. 【F:backend/auth/jwt.py†L43-L88】
11. **[security]** The JWT secret should be provided via `JWT_SECRET`; the default is explicitly flagged as insecure. 【F:backend/config.py†L17-L42】【F:backend/core/security.py†L41-L49】
12. **[schema]** `owners.lot` is unique and non-null. 【F:backend/models/models.py†L167-L176】
13. **[schema]** `owners.primary_name` and `owners.property_address` are required. 【F:backend/models/models.py†L167-L176】
14. **[data]** The default billing policy named `default` must exist and maintain the expected tier sequences. Startup code upserts this policy and its tiers. 【F:backend/constants.py†L24-L53】【F:backend/main.py†L214-L238】
15. **[data]** Notice types seed data is kept in sync with `NOTICE_TYPE_SEED`; startup will update existing records to match. 【F:backend/main.py†L240-L302】
16. **[runtime]** The database schema must either be empty or tracked by Alembic; otherwise bootstrap exits to prevent running migrations on an untracked schema. 【F:scripts/bootstrap_migrations.py†L80-L121】

## Findings (no code changes)

1. Migration `0003_seed_admin_user.py` seeds a fixed admin user with password `changeme`. This is convenient for bootstrapping but would be unsafe if applied in production without rotation. 【F:backend/migrations/versions/0003_seed_admin_user.py†L1-L125】
2. `JWT_SECRET` defaults to an insecure value in config; production should always set a strong secret via environment variables. 【F:backend/config.py†L17-L42】【F:backend/core/security.py†L41-L49】
3. Audit logging only covers HTTP write methods; background jobs or internal service actions are not automatically recorded unless they call `audit_log` directly. 【F:backend/main.py†L234-L271】【F:backend/services/audit.py†L1-L36】
