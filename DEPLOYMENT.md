# Production deployment and data continuity

A GitHub build deploys application code only. It does not contain the university's PostgreSQL records: users, role assignments, programmes, course offerings, sections, applications, and finance records remain in the database.

Before replacing a production release, DevOps must retain the PostgreSQL data directory mounted at `/data/postgres`, or back up and restore the database. Do not run `docker compose down -v` against the production database and do not replace `/data/postgres` when deploying a new image.

## Release procedure

1. Back up the database from the server.

   ```sh
   docker exec icms-db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > icms-before-release.dump
   ```

2. Deploy the new backend and frontend image tags in the server `.env`, then run:

   ```sh
   docker compose -f docker-compose.prod.yml up -d
   docker compose -f docker-compose.prod.yml ps
   ```

   The backend applies additive schema migrations at startup. Production uses `DEMO_DATA_ENABLED=false` and `PROVISION_PAYROLL_DATA=false`; demo seeds must never populate a live university database.

3. For a new server, restore the approved production backup before users access the application. A fresh database cannot display institutional roles, programmes, or sections simply because a frontend image was built.

   ```sh
   cat icms-approved.dump | docker exec -i icms-db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists
   ```

4. Verify the database contains active user accounts and role assignments, programmes, course offerings, and class sections. For admission conversion, the selected programme's department must have a class section. ICMS now reports this directly in the final class-allocation dialog when none exist.

Never copy a local development database or demo credentials to production.
