# Change Strategy

## Migrations vs. Bootstrap Scripts

- **Migrations** are only for schema evolution and data backfills required to keep the schema valid.
  - Avoid non-idempotent data seeding in migrations.
  - Prefer adding defaults and backfilling only when required to satisfy constraints.
- **Bootstrap scripts** are for environment setup and seeding data.
  - Keep them idempotent and safe to run multiple times.
  - Use them to create initial users, reference data, and sample content.

## Seeding Going Forward

- All new seeding should happen in a **bootstrap script**, not in migrations.
- Migrations should only ensure the schema can be applied to a clean database and upgraded safely.
