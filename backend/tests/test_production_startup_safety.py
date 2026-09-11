import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


class ProductionStartupSafetyTests(unittest.TestCase):
    """A production process must never seed tenants or operational records."""

    def test_production_startup_creates_schema_without_seeding_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "production-startup.db"
            environment = os.environ.copy()
            environment.update({
                "ENVIRONMENT": "production",
                "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
                "PYTHONPATH": str(BACKEND_DIR),
            })
            probe = """
import main
from database import SessionLocal
from models import Tenant, User
main._startup()
session = SessionLocal()
print(session.query(Tenant).count(), session.query(User).count())
session.close()
"""
            result = subprocess.run(
                [sys.executable, "-c", probe], cwd=BACKEND_DIR,
                env=environment, text=True, capture_output=True, check=True,
            )
            self.assertEqual(result.stdout.strip(), "0 0")

    def test_production_default_does_not_allow_wildcard_cors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "production-cors.db"
            environment = os.environ.copy()
            environment.update({
                "ENVIRONMENT": "production",
                "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
                "PYTHONPATH": str(BACKEND_DIR),
            })
            environment.pop("CORS_ORIGINS", None)
            result = subprocess.run(
                [sys.executable, "-c", "import main; print(main.CORS_ORIGINS)"],
                cwd=BACKEND_DIR, env=environment, text=True,
                capture_output=True, check=True,
            )
            self.assertEqual(result.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
