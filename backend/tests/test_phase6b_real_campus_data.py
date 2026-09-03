import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import AuditLog, OrgScope
from core import write_audit
import domain_api
import main


class Phase6BRealCampusDataTests(unittest.TestCase):
    campus_ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "Main Campus", "office_n": 3, "auth_level": "mfa"}

    def setUp(self):
        self.s = SessionLocal()
        self.audit_tenant = "p6b_audit_tenant"
        self.audit_scope = "p6b_audit_scope"

    def tearDown(self):
        # Do not delete append-only audit rows. The isolated tenant is reused
        # idempotently so its chain remains independently verifiable.
        self.s.close()

    def test_main_campus_seeded_records_and_audits_are_visible_only_to_main_campus(self):
        assets = domain_api.list_assets(ctx=self.campus_ctx, s=self.s)
        drives = domain_api.placements(ctx=self.campus_ctx, s=self.s)
        audit = main.get_audit(ctx=self.campus_ctx, s=self.s)
        self.assertEqual({row["id"] for row in assets["assets"]}, {"p6b_asset_main_lab_server", "p6b_asset_main_library_hvac"})
        self.assertEqual({row["id"] for row in drives["drives"]}, {"p6b_drive_main_techworks", "p6b_drive_main_greenline"})
        self.assertTrue(all(row["campus_scope_id"] == "scope_main_campus" for row in audit["entries"]))
        self.assertEqual({row["entity"] for row in audit["entries"] if "p6b_" in row["entity"]}, {
            "asset:p6b_asset_main_lab_server", "asset:p6b_asset_main_library_hvac",
            "placement_drive:p6b_drive_main_techworks", "placement_drive:p6b_drive_main_greenline"})

    def test_null_and_other_campus_records_are_excluded(self):
        assets = domain_api.list_assets(ctx=self.campus_ctx, s=self.s)
        drives = domain_api.placements(ctx=self.campus_ctx, s=self.s)
        self.assertTrue(all(row.campus_scope_id == "scope_main_campus" for row in
                            self.s.query(domain_api.D.Asset).filter(domain_api.D.Asset.id.in_([item["id"] for item in assets["assets"]])).all()))
        self.assertTrue(all(row.campus_scope_id == "scope_main_campus" for row in
                            self.s.query(domain_api.D.PlacementDrive).filter(domain_api.D.PlacementDrive.id.in_([item["id"] for item in drives["drives"]])).all()))
        self.assertEqual(self.s.query(AuditLog).filter(AuditLog.tenant_id == TENANT, AuditLog.campus_scope_id.is_(None)).count() > 0, True)

    def test_scoped_audit_entries_are_append_only_and_verify_with_tenant_chain(self):
        if not self.s.get(OrgScope, self.audit_scope):
            self.s.add(OrgScope(id=self.audit_scope, tenant_id=self.audit_tenant, level="campus", name="P6B Audit Campus")); self.s.commit()
        if not self.s.query(AuditLog).filter(AuditLog.tenant_id == self.audit_tenant).first():
            write_audit(self.s, "p6b_test", "Phase 6B test", 3, "asset.create", "asset:p6b-test", "", "in-service",
                        "Scoped test operation", tenant_id=self.audit_tenant, campus_scope_id=self.audit_scope)
        result = main.verify_audit(ctx={"tenant_id": self.audit_tenant, "office_n": 3, "scope_level": "campus", "scope_ref": self.audit_scope}, s=self.s)
        self.assertTrue(result["intact"], result)
        self.assertEqual(result["scope_count"], 1)
        self.assertEqual(result["campus_scope_id"], self.audit_scope)


if __name__ == "__main__":
    unittest.main()
