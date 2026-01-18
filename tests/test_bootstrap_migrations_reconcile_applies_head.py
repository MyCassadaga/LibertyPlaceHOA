import sqlalchemy as sa

from scripts import bootstrap_migrations


def test_bootstrap_reconcile_applies_two_factor_secret(tmp_path, monkeypatch):
    db_path = tmp_path / "reconcile.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    bootstrap_migrations.main()

    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("users")}
        assert "two_factor_secret" in columns
    finally:
        engine.dispose()
