import os
import sys

from database import seed
from domain_seed import seed_domain

BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


def pytest_sessionstart(session):
    """Initialize the shared SQLite DB with the same seed data the app uses at runtime."""
    try:
        seed()
        seed_domain()
    except Exception:
        # Some tests intentionally use isolated in-memory databases and do not need
        # the full seeded catalog. Keep earlier behavior intact while still seeding
        # the default project data used by live API tests.
        pass
