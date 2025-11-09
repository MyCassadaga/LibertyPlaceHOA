# Phase 1 Scope

## Delivered in Phase 1
- **RBAC foundations**: Roles for HOMEOWNER, BOARD, TREASURER, SECRETARY, ARC, AUDITOR, ATTORNEY, SYSADMIN with middleware helpers (`require_roles`, `require_minimum_role`).
- **Auth flow**: JWT login, SYSADMIN-restricted registration, `/auth/me` endpoint, bcrypt password hashing.
- **Audit logging**: Central helper logs all sensitive create/update actions with before/after snapshots.
- **Homeowner directory**: CRUD endpoints, homeowner self-service update requests with approval workflow, and board review queue.
- **Billing & ledger**: Invoice/payment models, ledger entries, late fee utility, CSV-friendly ledger helper, summary metrics endpoint.
- **Communications**: Announcement endpoint that logs deliveries, stubs email sending, and generates PDF placeholder for print packets.
- **Contracts repository**: CRUD endpoints for vendor contracts with renewal metadata.
- **Frontend portal**: Login, dashboard, billing views, contracts list (board-only), owner directory (board-only), homeowner profile change requests, communications creation UI.
- **Developer tooling**: Alembic initial migration, role seeding at startup, management script to create the first SYSADMIN.

## Deferred to Later Phases
- Real email/PDF generation and address label exports (stubs in place).
- Payment processor integration and homeowner self-service payment submission with validation.
- Advanced reporting, QuickBooks export automation, and Postgres production hardening.
- Two-factor authentication and persistent sessions.
- Automated test coverage and CI/CD pipeline.
