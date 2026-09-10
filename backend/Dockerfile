FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# main.py applies additive migrations at startup. Development fixture seeding is
# explicitly gated by DEMO_DATA_ENABLED and is disabled by docker-compose.
CMD ["sh", "-c", "if [ \"$PROVISION_PAYROLL_DATA\" = \"true\" ]; then python -c 'from database import SessionLocal, ensure_additive_schema, ensure_versioned_migrations, seed; from domain_seed import seed_domain, _ensure_payroll_staff_logins, _seed_non_teaching_staff_records, _seed_payroll_demo_data; from portal_api import _ensure_payroll_run_entries; import domain_models as D; seed(); ensure_versioned_migrations(); ensure_additive_schema();\ntry: seed_domain()\nexcept Exception as exc: print(f\"domain seed warning: {exc}\", flush=True)\ns=SessionLocal(); _seed_non_teaching_staff_records(s); s.commit(); _seed_payroll_demo_data(s); s.commit()\ntry: _ensure_payroll_staff_logins(s); s.commit()\nexcept Exception as exc: s.rollback(); print(f\"payroll login warning: {exc}\", flush=True)\n_seed_payroll_demo_data(s); s.commit()\nfor run in s.query(D.PayrollRun).all(): _ensure_payroll_run_entries(s, run)\ns.commit(); s.close()'; fi; exec uvicorn main:app --host 0.0.0.0 --port 8000"]
