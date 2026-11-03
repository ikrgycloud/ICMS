VERSION = "0067_normalize_academic_calendar_status"


def upgrade(engine):
    """Canonicalize legacy calendar states before workflow filtering uses them."""
    from sqlalchemy import inspect, text

    if "academic_calendar_entries" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE academic_calendar_entries
            SET status = 'Published'
            WHERE lower(status) = 'published'
        """))
