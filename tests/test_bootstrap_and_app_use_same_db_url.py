import sqlalchemy as sa

import backend.config as app_config
from scripts import bootstrap_migrations


def test_bootstrap_and_app_use_same_db_url(tmp_path, monkeypatch):
    db_path = tmp_path / "bootstrap_app_same.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    bootstrap_migrations.main()

    settings = app_config.build_settings()
    resolved_url = app_config.get_database_url(settings_obj=settings)
    bootstrap_url = bootstrap_migrations.get_database_url()

    assert bootstrap_url == resolved_url
    assert app_config.get_database_url_fingerprint(database_url=resolved_url).endswith(
        str(db_path.resolve())
    )

    engine = sa.create_engine(resolved_url)
    try:
        inspector = sa.inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("users")}
        assert "two_factor_secret" in columns
    finally:
        engine.dispose()
