"""Phase 3 eligibility evaluation auditability; additive only."""
from sqlalchemy import inspect, text
VERSION = "0005_admissions_eligibility"
def upgrade(engine):
    import domain_models
    from models import Base
    Base.metadata.create_all(engine)
    adds = {"application_eligibility_checks": [("quota_id", "VARCHAR"), ("evaluation_run_id", "VARCHAR"), ("rule_version", "INTEGER DEFAULT 1")], "admission_quotas": [("program_id", "VARCHAR"), ("description", "TEXT DEFAULT ''"), ("priority", "INTEGER DEFAULT 0")]}
    with engine.begin() as c:
        i=inspect(c)
        for t, cols in adds.items():
            existing={x['name'] for x in i.get_columns(t)}
            for n,d in cols:
                if n not in existing: c.execute(text(f"ALTER TABLE {t} ADD COLUMN {n} {d}"))
        c.execute(text("CREATE INDEX IF NOT EXISTS ix_eligibility_checks_run ON application_eligibility_checks (evaluation_run_id)"))
def downgrade(engine): return None
