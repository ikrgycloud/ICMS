"""Add soft-deactivation state to transport routes."""
VERSION = "v0008_transport_route_status"

from sqlalchemy import inspect, text


def upgrade(engine):
    if "transport_routes" not in inspect(engine).get_table_names():
        return
    columns = {c["name"] for c in inspect(engine).get_columns("transport_routes")}
    if "status" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transport_routes ADD COLUMN status VARCHAR DEFAULT 'active'"))
            conn.execute(text("UPDATE transport_routes SET status = 'active' WHERE status IS NULL"))
