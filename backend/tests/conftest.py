"""Isolated integration-test environment for the ICMS backend.

The test modules exercise the real HTTP API and also create fixtures through
``SessionLocal``.  Both therefore need to use the same database.  Pytest owns
this SQLite file and a private Uvicorn process; it never reuses Docker's
development PostgreSQL database on port 8000.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib import request


BACKEND_DIR = Path(__file__).resolve().parents[1]
# A process-specific name prevents a stale Windows SQLite handle from one
# interrupted pytest run affecting the next one.
TEST_DB_PATH = Path(os.environ.get("ICMS_PYTEST_DB_PATH", BACKEND_DIR / f".pytest_icms_{os.getpid()}.sqlite3"))
TEST_API_LOG_PATH = BACKEND_DIR / f".pytest_icms_{os.getpid()}.api.log"
TEST_API_URL = os.environ.get("ICMS_TEST_API_URL", "")
if not TEST_API_URL:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _port_probe:
        _port_probe.bind(("127.0.0.1", 0))
        TEST_PORT = _port_probe.getsockname()[1]
    TEST_API_URL = f"http://127.0.0.1:{TEST_PORT}"
else:
    TEST_PORT = urlparse(TEST_API_URL).port

# This runs while pytest imports conftest, before it imports the test modules
# (which import database.SessionLocal).
os.environ["ICMS_PYTEST_DB_PATH"] = str(TEST_DB_PATH)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["ICMS_TEST_API_URL"] = TEST_API_URL
os.environ["ICMS_TEST_SKIP_STARTUP_SEED"] = "1"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _wait_for_server(process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = TEST_API_LOG_PATH.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"The isolated ICMS test API exited during startup:\n{output}")
        try:
            with request.urlopen(f"{TEST_API_URL}/docs", timeout=1):
                return
        except Exception:
            time.sleep(0.25)
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    output = TEST_API_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError(f"Timed out waiting for the isolated ICMS test API:\n{output}")


def pytest_configure(config) -> None:
    if os.environ.get("ICMS_PYTEST_SERVER_STARTED") == "1":
        return
    import domain_models  # noqa: F401 - register every domain mapper with Base.metadata.
    import domain_models as D
    from database import SessionLocal, seed
    from domain_seed import seed_domain
    from models import User

    seed()
    seed_domain()

    # Legacy regression tests use the generic ``professor`` demonstration
    # account. Keep it mapped to a real, active, roster-backed faculty member
    # in the disposable test database. The named phase fixtures (Aarav, HOD,
    # coordinator, and so on) retain their normal seed mappings.
    db = SessionLocal()
    try:
        professor = db.query(User).filter(User.username == "professor").one()
        hod = db.query(User).filter(User.username == "hod").one()
        candidate = (db.query(D.StaffMember)
                     .join(D.TeachingAllocation, D.TeachingAllocation.faculty_id == D.StaffMember.id)
                     .join(D.Enrollment, D.Enrollment.section_id == D.TeachingAllocation.section_id)
                     .filter(D.TeachingAllocation.status == "active",
                             D.Enrollment.status == "enrolled",
                             D.StaffMember.user_id.is_(None),
                             D.StaffMember.id != "staff_fac_1")
                     .order_by(D.StaffMember.id)
                     .first())
        if not candidate:
            raise RuntimeError("Test seed has no active faculty allocation with an enrolled roster")
        candidate.user_id = professor.id
        candidate.office_n = 11
        professor.role = candidate.name
        professor.scope_ref = candidate.dept_id
        db.commit()
    finally:
        db.close()

    environment = os.environ.copy()
    with TEST_API_LOG_PATH.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(TEST_PORT)],
            cwd=BACKEND_DIR,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    config._icms_test_api_process = process
    os.environ["ICMS_PYTEST_SERVER_STARTED"] = "1"
    _wait_for_server(process)


def pytest_sessionfinish(session, exitstatus) -> None:
    process = getattr(session.config, "_icms_test_api_process", None)
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    # It is a per-process, pytest-owned file. A failed unlink is harmless on
    # Windows because the next invocation uses a fresh filename.
    try:
        from database import engine
        engine.dispose()
        TEST_DB_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    os.environ.pop("ICMS_PYTEST_SERVER_STARTED", None)


