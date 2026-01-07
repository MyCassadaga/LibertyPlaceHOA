# Codex Contract

## Non-Negotiable Rules

- **Must** never edit old migrations that have shipped.
- **Must** ensure seed steps are idempotent.
- **Must** never hardcode `user_id = 1` assumptions.
- **Must** satisfy any `NOT NULL` column in inserts (defaults or explicit values).
- **Must** ensure migrations work on a brand-new empty database.
- **Must** ensure the Render start command succeeds without manual DB intervention.

## Required Workflow (Every Change)

- **Phase 0: Understand**
  - Reference `docs/ARCHITECTURE_MAP.md` and identify the affected areas.
- **Phase 1: Reproduce**
  - State the exact error, line, or invariant violated.
- **Phase 2: Minimal Fix**
  - Implement the smallest possible diff that resolves the issue.
- **Phase 3: Prove**
  - Run tests or smoke checks and report results.
- **Phase 4: Risk**
  - Document what could break in production.

## Stop Conditions

- If migration history is inconsistent or missing revisions: **stop** and propose a safe reset plan.
- If the DB has tables but `alembic_version` is missing: **stop** and propose options.
