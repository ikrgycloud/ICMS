"""Add Administration Finance reservations and commitments over BudgetLine."""
VERSION = "0036_administration_finance_controls"


def upgrade(engine):
    from sqlalchemy import inspect, text
    from models import Base
    import administration_models  # noqa: F401

    columns = {column["name"] for column in inspect(engine).get_columns("budget_lines")}
    with engine.begin() as connection:
        if "reserved" not in columns:
            connection.execute(text("ALTER TABLE budget_lines ADD COLUMN reserved FLOAT DEFAULT 0"))
        if "committed" not in columns:
            connection.execute(text("ALTER TABLE budget_lines ADD COLUMN committed FLOAT DEFAULT 0"))
    Base.metadata.create_all(engine, tables=[administration_models.AdministrativeFinanceReservation.__table__, administration_models.AdministrativeFinanceCommitment.__table__])


def downgrade(engine):
    return None