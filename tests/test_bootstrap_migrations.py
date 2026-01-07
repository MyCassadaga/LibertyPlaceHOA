import sqlalchemy as sa

from scripts import bootstrap_migrations


def test_sanitize_database_url_strips_psql_wrapper_and_quotes():
    raw = "psql 'postgresql://user:pass@host:5432/hoa'"
    assert (
        bootstrap_migrations.sanitize_database_url(raw)
        == "postgresql://user:pass@host:5432/hoa"
    )


def test_bootstrap_resets_missing_revision_and_stamps_head(tmp_path, monkeypatch):
    db_path = tmp_path / "bootstrap.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            connection.execute(
                sa.text("INSERT INTO alembic_version (version_num) VALUES ('8b0c74c7f5ce')")
            )
    finally:
        engine.dispose()

    calls = []

    def fake_run_alembic(*args: str) -> None:
        calls.append(args)

    monkeypatch.setattr(bootstrap_migrations, "get_repo_head_revision", lambda: "0001_baseline")
    monkeypatch.setattr(bootstrap_migrations, "get_known_revisions", lambda: {"0001_baseline"})
    monkeypatch.setattr(bootstrap_migrations, "run_alembic", fake_run_alembic)

    bootstrap_migrations.main()

    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        assert "alembic_version" not in inspector.get_table_names()
    finally:
        engine.dispose()

    assert calls == [("stamp", "head"), ("upgrade", "head")]
