import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import backend.config as app_config
import backend.main as app_main
from scripts import bootstrap_migrations


def test_render_bootstrap_smoke(tmp_path, monkeypatch):
    db_path = tmp_path / "render_bootstrap.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    bootstrap_migrations.main()

    engine = sa.create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)

    previous_engine = app_config.engine
    previous_session_local = app_config.SessionLocal
    previous_database_url = app_config.settings.database_url
    previous_main_engine = app_main.engine
    previous_main_session_local = app_main.SessionLocal
    try:
        app_config.engine = engine
        app_config.SessionLocal = SessionLocal
        app_config.settings.database_url = database_url
        app_main.engine = engine
        app_main.SessionLocal = SessionLocal

        with TestClient(app_main.app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        app_main.engine = previous_main_engine
        app_main.SessionLocal = previous_main_session_local
        app_config.engine = previous_engine
        app_config.SessionLocal = previous_session_local
        app_config.settings.database_url = previous_database_url
        engine.dispose()
