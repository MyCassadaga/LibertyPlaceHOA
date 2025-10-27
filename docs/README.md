# Documentation Index

- [PHASE1_SCOPE](./PHASE1_SCOPE.md): Summary of requirements covered in this MVP and what remains for later phases.
- Backend:
  - Auth: JWT with role enforcement (`backend/auth/jwt.py`).
  - Models & migrations: SQLAlchemy models in `backend/models/models.py`, Alembic migration `backend/migrations/versions/0001_initial.py`.
  - Services: billing ledger helpers, audit logging, and placeholders for email/PDF.
- Frontend:
  - React application bootstrapped via Vite with Tailwind styling.
  - Auth context stored in memory (improvement roadmap includes refresh tokens / 2FA).
  - Pages: login, dashboard, billing, owner profile, contracts, communications, owners directory.

Refer to the root `README.md` for setup commands and environment requirements.
