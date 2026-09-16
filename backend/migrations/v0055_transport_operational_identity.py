"""Persist route codes used by the operational transport workflow."""
from sqlalchemy import inspect, text

VERSION = "0055_transport_operational_identity"


def upgrade(engine):
    if not inspect(engine).has_table("transport_routes"):
        return
    with engine.begin() as conn:
        columns = {column["name"] for column in inspect(conn).get_columns("transport_routes")}
        if "route_code" not in columns:
            conn.execute(text("ALTER TABLE transport_routes ADD COLUMN route_code VARCHAR DEFAULT ''"))
        conn.execute(text("UPDATE transport_routes SET route_code = UPPER(SUBSTR(id, 1, 6)) WHERE route_code IS NULL OR route_code = ''"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transport_routes_route_code ON transport_routes (route_code)"))


def downgrade(engine):
    return None
