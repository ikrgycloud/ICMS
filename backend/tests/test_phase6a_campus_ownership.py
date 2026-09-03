import os
import sys
import unittest
from datetime import date, datetime

from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal, TENANT
from models import OrgScope
import domain_api
import domain_models as D


class Phase6ACampusOwnershipTests(unittest.TestCase):
    campus_ctx = {"sub": "user_3", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "scope_main_campus", "office_n": 3, "auth_level": "mfa"}
    empty_campus_ctx = {**campus_ctx, "scope_ref": "scope_city_campus"}
    principal_ctx = {"sub": "user_4", "tenant_id": TENANT, "scope_level": "campus", "scope_ref": "Main Campus", "office_n": 4, "auth_level": "mfa"}
    vc_ctx = {"sub": "user_2", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 2, "auth_level": "mfa"}
    chairman_ctx = {"sub": "user_1", "tenant_id": TENANT, "scope_level": "university", "scope_ref": "scope_univ", "office_n": 1, "auth_level": "mfa"}

    def setUp(self):
        self.s = SessionLocal()
        self.stamp = datetime.utcnow().strftime("%H%M%S%f")
        self.asset_ids, self.drive_ids, self.scope_ids = [], [], []

    def tearDown(self):
        self.s.rollback()
        self.s.query(D.Asset).filter(D.Asset.id.in_(self.asset_ids)).delete(synchronize_session=False)
        self.s.query(D.PlacementDrive).filter(D.PlacementDrive.id.in_(self.drive_ids)).delete(synchronize_session=False)
        self.s.query(OrgScope).filter(OrgScope.id.in_(self.scope_ids)).delete(synchronize_session=False)
        self.s.commit()
        self.s.close()

    def add_records(self):
        other_tenant = f"p6a_tenant_{self.stamp}"
        other_scope_id = f"p6a_scope_{self.stamp}"
        self.s.add(OrgScope(id=other_scope_id, tenant_id=other_tenant, level="campus", name="P6A Other Campus"))
        self.scope_ids.append(other_scope_id)
        specs = [
            ("main", TENANT, "scope_main_campus"),
            ("north", TENANT, "scope_north_campus"),
            ("unowned", TENANT, None),
            ("other_tenant", other_tenant, other_scope_id),
        ]
        for label, tenant_id, scope_id in specs:
            asset_id, drive_id = f"p6a_asset_{label}_{self.stamp}", f"p6a_drive_{label}_{self.stamp}"
            self.s.add(D.Asset(id=asset_id, tenant_id=tenant_id, campus_scope_id=scope_id,
                               tag=asset_id[-12:], name=label, category="P6A", location="Verified", status="in-service", value=100))
            self.s.add(D.PlacementDrive(id=drive_id, tenant_id=tenant_id, campus_scope_id=scope_id,
                                        company=label, role="P6A", ctc=10, date=date(2026, 9, 1), offers=1))
            self.asset_ids.append(asset_id); self.drive_ids.append(drive_id)
        self.s.commit()

    def test_models_declare_nullable_indexed_org_scope_foreign_keys(self):
        for model in (D.Asset, D.PlacementDrive):
            column = model.__table__.c.campus_scope_id
            self.assertTrue(column.nullable)
            self.assertTrue(column.index)
            self.assertEqual({fk.target_fullname for fk in column.foreign_keys}, {"org_scopes.id"})

    def test_campus_head_receives_only_own_authoritatively_owned_records(self):
        self.add_records()
        assets = domain_api.list_assets(ctx=self.campus_ctx, s=self.s)
        drives = domain_api.placements(ctx=self.campus_ctx, s=self.s)
        self.assertEqual([row["name"] for row in assets["assets"] if row["name"] in ("main", "north", "unowned")], ["main"])
        self.assertEqual([row["company"] for row in drives["drives"] if row["company"] in ("main", "north", "unowned")], ["main"])
        self.assertEqual(assets["campus_scope_id"], "scope_main_campus")
        self.assertEqual(drives["campus_scope_id"], "scope_main_campus")

    def test_unowned_records_produce_truthful_unavailable_state(self):
        asset_id, drive_id = f"p6a_asset_unowned_{self.stamp}", f"p6a_drive_unowned_{self.stamp}"
        self.s.add_all([
            D.Asset(id=asset_id, tenant_id=TENANT, tag=asset_id[-12:], name="unowned", campus_scope_id=None),
            D.PlacementDrive(id=drive_id, tenant_id=TENANT, company="unowned", campus_scope_id=None),
        ])
        self.s.commit(); self.asset_ids.append(asset_id); self.drive_ids.append(drive_id)
        self.assertEqual(domain_api.list_assets(ctx=self.empty_campus_ctx, s=self.s)["data_status"], "unavailable")
        self.assertEqual(domain_api.placements(ctx=self.empty_campus_ctx, s=self.s)["data_status"], "unavailable")

    def test_assignment_validation_rejects_invalid_and_cross_tenant_scopes(self):
        other_scope = f"p6a_scope_{self.stamp}"
        self.s.add(OrgScope(id=other_scope, tenant_id=f"p6a_tenant_{self.stamp}", level="campus", name="Other"))
        self.s.commit(); self.scope_ids.append(other_scope)
        self.assertEqual(domain_api._validated_campus_scope_assignment(self.s, TENANT, "scope_main_campus").id, "scope_main_campus")
        for scope_id in ("not-a-scope", other_scope):
            with self.assertRaises(HTTPException) as error:
                domain_api._validated_campus_scope_assignment(self.s, TENANT, scope_id)
            self.assertEqual(error.exception.status_code, 422)

    def test_principal_vc_and_chairman_keep_tenant_wide_access(self):
        self.add_records()
        for ctx in (self.principal_ctx, self.vc_ctx, self.chairman_ctx):
            self.assertIn("main", [row["name"] for row in domain_api.list_assets(ctx=ctx, s=self.s)["assets"]])
            self.assertIn("main", [row["company"] for row in domain_api.placements(ctx=ctx, s=self.s)["drives"]])
            self.assertNotIn("other_tenant", [row["name"] for row in domain_api.list_assets(ctx=ctx, s=self.s)["assets"]])
            self.assertNotIn("other_tenant", [row["company"] for row in domain_api.placements(ctx=ctx, s=self.s)["drives"]])


if __name__ == "__main__":
    unittest.main()
