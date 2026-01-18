import subprocess

from backend import config as app_config
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import URL, make_url

ALEMBIC_CONFIG = "backend/alembic.ini"


def run_alembic(*args: str) -> None:
    cmd = ["alembic", "-c", ALEMBIC_CONFIG, *args]
    print("RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def get_repo_head_revision() -> str:
    cmd = ["alembic", "-c", ALEMBIC_CONFIG, "heads"]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    heads = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        revision = stripped.split()[0]
        heads.append(revision)
    unique_heads = sorted(set(heads))
    if len(unique_heads) != 1:
        raise SystemExit(
            "BOOTSTRAP: expected exactly one alembic head; "
            f"found {', '.join(unique_heads) or 'none'}"
        )
    return unique_heads[0]


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
    settings = app_config.build_settings()
    database_url = app_config.get_database_url(settings_obj=settings)
    sanitized = sanitize_database_url(database_url)
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
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            return None
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            if row is None:
                return None
            return row[0]
    finally:
        engine.dispose()


def get_tables(database_url: str) -> list[str]:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        return inspector.get_table_names()
    finally:
        engine.dispose()


def drop_alembic_version_table(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            return False
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
        return True
    finally:
        engine.dispose()


def reset_missing_revision(
    database_url: str,
    repo_head: str,
    known_revisions: set[str],
    tables: list[str],
) -> bool:
    has_version_table = "alembic_version" in tables
    user_tables = [table for table in tables if table != "alembic_version"]
    db_revision = get_database_revision(database_url) if has_version_table else None

    print(
        f"BOOTSTRAP: database revision = {db_revision or 'missing'}",
        flush=True,
    )
    print(f"BOOTSTRAP: repo head revision = {repo_head}", flush=True)

    invalid_revision = not has_version_table or not db_revision or db_revision not in known_revisions
    if invalid_revision and user_tables:
        print(
            "BOOTSTRAP: detected existing tables with missing/invalid alembic_version; "
            "manual confirmation required before resetting migrations.",
            flush=True,
        )
        raise SystemExit(1)

    if has_version_table and db_revision == repo_head:
        return False

    if db_revision and db_revision in known_revisions:
        return False

    if invalid_revision and not user_tables:
        dropped = drop_alembic_version_table(database_url)
        print(
            "BOOTSTRAP: alembic_version reset; "
            f"dropped={dropped}.",
            flush=True,
        )
        run_alembic("upgrade", "head")
        return True

    return False


def main() -> None:
    database_url = get_database_url()
    db_fingerprint = app_config.get_database_url_fingerprint(database_url=database_url)
    print(f"BOOTSTRAP: database fingerprint = {db_fingerprint}", flush=True)
    tables = get_tables(database_url)
    known_revisions = get_known_revisions()
    repo_head = get_repo_head_revision()
    current_revision = get_database_revision(database_url)
    print(
        f"BOOTSTRAP: current revision before upgrade = {current_revision or 'missing'}",
        flush=True,
    )
    print(f"BOOTSTRAP: repo head revision = {repo_head}", flush=True)
    reset_done = reset_missing_revision(database_url, repo_head, known_revisions, tables)
    if not reset_done:
        enforce_empty_or_tracked_schema(database_url)
        run_alembic("upgrade", "head")
    upgraded_revision = get_database_revision(database_url)
    print(
        f"BOOTSTRAP: current revision after upgrade = {upgraded_revision or 'missing'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
