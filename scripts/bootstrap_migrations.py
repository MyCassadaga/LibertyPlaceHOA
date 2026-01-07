import argparse
import os
import subprocess
from typing import Tuple

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import URL, make_url

ALEMBIC_CONFIG = "backend/alembic.ini"
REVISION_MULTI_ROLE = "0008_multi_role_accounts"
REVISION_ARC_NOTIFICATION = "0016_arc_request_notification_columns"
REVISION_BUDGETS = "7a73908faa2a_budget_and_reserve"

SENTINEL_REVISIONS = (
    ("budgets", None, REVISION_BUDGETS, "budgets table"),
    ("arc_requests", "decision_notified_at", REVISION_ARC_NOTIFICATION, "arc_requests.decision_notified_at"),
    ("user_roles", None, REVISION_MULTI_ROLE, "user_roles table"),
)


def run_alembic(*args: str) -> None:
    cmd = ["alembic", "-c", ALEMBIC_CONFIG, *args]
    print("RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


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


def get_database_url() -> Tuple[str, URL]:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise SystemExit("BOOTSTRAP: DATABASE_URL is required")
    sanitized = sanitize_database_url(raw)
    if sanitized.startswith("psql "):
        raise SystemExit("BOOTSTRAP: DATABASE_URL must be a SQLAlchemy URL, not a psql wrapper")
    url = validate_database_url(sanitized)
    log_connection_target(url)
    return sanitized, url


def has_table(inspector, name: str) -> bool:
    return inspector.has_table(name)


def detect_applied_revision(inspector) -> Tuple[str | None, str | None]:
    for table, column, revision, reason in SENTINEL_REVISIONS:
        if not has_table(inspector, table):
            continue
        if column:
            column_names = {col["name"] for col in inspector.get_columns(table)}
            if column not in column_names:
                continue
        return revision, reason
    return None, None


def has_any_tables(inspector) -> bool:
    return bool(inspector.get_table_names())


def get_current_revision(inspector, connection) -> str | None:
    if not has_table(inspector, "alembic_version"):
        return None
    result = connection.execute(text("SELECT version_num FROM alembic_version"))
    row = result.fetchone()
    return row[0] if row else None


def run_diagnostics(database_url: str) -> None:
    run_alembic("current")
    run_alembic("heads")
    run_alembic("history", "--verbose")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        with engine.connect() as connection:
            dialect = engine.dialect.name
            if dialect == "postgresql":
                table_sql = text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :table)"
                )
                column_sql = text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :table AND column_name = :column)"
                )
            elif dialect == "sqlite":
                table_sql = text(
                    "SELECT EXISTS (SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :table)"
                )
                column_sql = text(
                    "SELECT EXISTS (SELECT 1 FROM pragma_table_info(:table) WHERE name = :column)"
                )
            else:
                table_sql = text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :table"
                )
                column_sql = text(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = :table AND column_name = :column"
                )

            def _sql_bool(statement, params):
                result = connection.execute(statement, params).scalar()
                return bool(result)

            print("BOOTSTRAP: diagnostics SQL checks", flush=True)
            print(
                f" - alembic_version exists: {_sql_bool(table_sql, {'table': 'alembic_version'})}",
                flush=True,
            )
            for table, column, _, _ in SENTINEL_REVISIONS:
                exists = _sql_bool(table_sql, {"table": table})
                detail = ""
                if column:
                    detail = f", column {column}: {_sql_bool(column_sql, {'table': table, 'column': column})}"
                print(f" - table {table}: {exists}{detail}", flush=True)
    finally:
        engine.dispose()


def reconcile(database_url: str) -> None:
    config = Config(ALEMBIC_CONFIG)
    script = ScriptDirectory.from_config(config)

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        with engine.connect() as connection:
            current_revision = get_current_revision(inspector, connection)

        if current_revision:
            try:
                script.get_revision(current_revision)
                print(
                    f"BOOTSTRAP: alembic_version present ({current_revision}); skipping stamp",
                    flush=True,
                )
                run_alembic("upgrade", "head")
                return
            except ResolutionError:
                print(
                    f"BOOTSTRAP: alembic_version {current_revision} not found in migration history",
                    flush=True,
                )
                raise SystemExit(
                    "BOOTSTRAP: alembic_version exists but does not match known revisions; "
                    "manual intervention required"
                )

        if has_any_tables(inspector):
            target_revision, reason = detect_applied_revision(inspector)
            if target_revision:
                print(
                    f"BOOTSTRAP: no alembic_version table; detected {reason} -> stamp {target_revision}",
                    flush=True,
                )
                run_alembic("stamp", target_revision)
            else:
                print(
                    "BOOTSTRAP: no alembic_version table and no known sentinel revisions detected; "
                    "running full upgrade",
                    flush=True,
                )
            run_alembic("upgrade", "head")
            return

        print("BOOTSTRAP: fresh database detected; running upgrade", flush=True)
        run_alembic("upgrade", "head")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Alembic migrations safely")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("reconcile", "diagnostics"),
        default="reconcile",
        help="Run reconciliation (default) or diagnostics",
    )
    args = parser.parse_args()

    database_url, _ = get_database_url()
    if args.command == "diagnostics":
        run_diagnostics(database_url)
    else:
        reconcile(database_url)


if __name__ == "__main__":
    main()
