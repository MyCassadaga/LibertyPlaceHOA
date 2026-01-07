import os
import subprocess

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import URL, make_url

ALEMBIC_CONFIG = "backend/alembic.ini"


def run_alembic(*args: str) -> None:
    cmd = ["alembic", "-c", ALEMBIC_CONFIG, *args]
    print("RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def get_script_directory() -> ScriptDirectory:
    config = Config(ALEMBIC_CONFIG)
    return ScriptDirectory.from_config(config)


def get_known_revisions() -> set[str]:
    script_directory = get_script_directory()
    return {revision.revision for revision in script_directory.walk_revisions()}


def sanitize_database_url(value: str) -> str:
    if not isinstance(value, str):
        return value
    normalized = value.strip().strip("'\"")
    if normalized.startswith("psql "):
        normalized = normalized[5:].strip()
    while (normalized.startswith("'") and normalized.endswith("'")) or (
        normalized.startswith('"') and normalized.endswith('"')
    ):
        normalized = normalized[1:-1].strip()
    return normalized.strip("'\"")


def validate_database_url(value: str) -> URL:
    try:
        return make_url(value)
    except Exception as exc:  # noqa: BLE001 - surface a clear error to callers
        raise SystemExit(
            f"BOOTSTRAP: DATABASE_URL is not a valid SQLAlchemy URL: {value!r}"
        ) from exc


def log_connection_target(url: URL) -> None:
    redacted = url.render_as_string(hide_password=True)
    host = url.host or "local"
    db_name = url.database or ""
    print(
        f"BOOTSTRAP: using database {redacted} (host={host}, db={db_name})",
        flush=True,
    )


def get_database_url() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise SystemExit("BOOTSTRAP: DATABASE_URL is required")
    sanitized = sanitize_database_url(raw)
    if sanitized.startswith("psql "):
        raise SystemExit("BOOTSTRAP: DATABASE_URL must be a SQLAlchemy URL, not a psql wrapper")
    url = validate_database_url(sanitized)
    log_connection_target(url)
    return sanitized


def enforce_empty_or_tracked_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        has_tables = bool(tables)
        has_version = inspector.has_table("alembic_version")
        if has_tables and not has_version:
            print(
                "BOOTSTRAP: detected existing tables without alembic_version; "
                "refusing to run migrations on an untracked schema.",
                flush=True,
            )
            raise SystemExit(1)
    finally:
        engine.dispose()


def get_database_revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            if row is None:
                return None
            return row[0]
    finally:
        engine.dispose()


def stamp_missing_revision(database_url: str) -> None:
    revision = get_database_revision(database_url)
    if not revision:
        return
    known_revisions = get_known_revisions()
    if revision not in known_revisions:
        print(
            "BOOTSTRAP: alembic_version references missing revision; "
            "stamping database to current head.",
            flush=True,
        )
        run_alembic("stamp", "head")


def main() -> None:
    database_url = get_database_url()
    enforce_empty_or_tracked_schema(database_url)
    stamp_missing_revision(database_url)
    run_alembic("upgrade", "head")


if __name__ == "__main__":
    main()
