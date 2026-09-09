"""Integration-test bootstrap.

The integration tests exercise the running API against the configured test
database.  Importing the test package makes schema setup deterministic when
the suite is launched directly with unittest discovery.
"""
from database import Base, engine, ensure_additive_schema, ensure_versioned_migrations
import domain_models  # noqa: F401 - register domain tables
import frontdesk_models  # noqa: F401 - register front-desk tables

Base.metadata.create_all(engine)
ensure_additive_schema()
ensure_versioned_migrations()
