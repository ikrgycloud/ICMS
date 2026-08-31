# ICMS Database

The ICMS backend uses **PostgreSQL 16** in production and falls back to a local
**SQLite** file for zero-config development. The schema and all reference data are
managed by the application itself — you normally never touch SQL directly.

## How the database is provisioned

On startup the backend (`backend/main.py`) runs a seed routine that:

1. Creates every table (see `schema.sql` for the physical layout).
2. Seeds the tenant, the organizational scope tree
   (global → university → campus → faculty → department → program → section),
   and the 21 permission verbs.
3. Loads all **40 offices → 268 internal roles** from `backend/catalog.json`
   and wires their role→permission grants from the RBAC matrix.
4. Seeds **40 demo user accounts** (one head per office).
5. Seeds the monetary **approval limits** per scope level.

The seed is idempotent — it detects an already-seeded database and skips.

## Connection

The backend reads `DATABASE_URL`:

| Environment | `DATABASE_URL` | Store |
|-------------|----------------|-------|
| Docker Compose | `postgresql://icms:icms_secret@db:5432/icms` | PostgreSQL |
| Local dev (unset) | *(falls back)* | `backend/icms.db` (SQLite) |

## Multi-tenancy

Every table carries a `tenant_id` column (shared-schema isolation). In production,
add PostgreSQL **Row-Level Security** policies keyed on `tenant_id`, as described
in the developer blueprint (Section 12), so tenants can never read each other's rows.

## Files

- `schema.sql` — PostgreSQL DDL reference, generated from the ORM models.
- The authoritative source of truth is the SQLAlchemy models in `backend/models.py`.
