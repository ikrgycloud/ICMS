"""Run backend tests against the Compose API and its PostgreSQL database.

Usage from the repository root:
  python backend/tests/run_docker_tests.py
"""
import os
import sys
import unittest

os.environ.setdefault("ICMS_API_URL", "http://127.0.0.1:8010")
os.environ.setdefault("DATABASE_URL", "postgresql://icms:icms_secret@127.0.0.1:5433/icms")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

suite = unittest.defaultTestLoader.discover(os.path.join(BACKEND, "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
