from pathlib import Path

from alembic import command
from alembic.config import Config
import backend.config as app_config
from backend.models.models import ARCRequest
import sqlalchemy as sa


def test_arc_request_migration_adds_notification_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "migrations.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(app_config.settings, "database_url", db_url, raising=False)

    config = Config(str(Path("backend/alembic.ini")))
    config.set_main_option("script_location", "backend/migrations")
    command.upgrade(config, "0016_arc_request_notification_columns")

    engine = sa.create_engine(db_url)
    try:
        inspector = sa.inspect(engine)
        column_names = {column["name"] for column in inspector.get_columns("arc_requests")}
        assert "decision_notified_at" in column_names
        assert "decision_notified_status" in column_names

        with sa.orm.Session(engine) as session:
            session.query(ARCRequest).all()
    finally:
        engine.dispose()
