import argparse
import os
import subprocess
from typing import Iterable, Tuple

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import URL, make_url

ALEMBIC_CONFIG = "backend/alembic.ini"
REVISION_MULTI_ROLE = "0008_multi_role_accounts"
REVISION_ARC_NOTIFICATION = "0016_arc_request_notification_columns"
REVISION_BUDGETS = "7a73908faa2a"
REVISION_CLICK2MAIL = "8b0c74c7f5ce"

SENTINEL_REVISIONS = (
    ("budgets", None, REVISION_BUDGETS, "budgets table"),
    ("arc_requests", "decision_notified_at", REVISION_ARC_NOTIFICATION, "arc_requests.decision_notified_at"),
    ("paperwork_items", "delivery_provider", REVISION_CLICK2MAIL, "paperwork_items.delivery_provider"),
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


def has_column(inspector, table: str, column: str) -> bool:
    return column in {col["name"] for col in inspector.get_columns(table)}


def detect_applied_revisions(inspector) -> list[Tuple[str, str]]:
    found: list[Tuple[str, str]] = []
    for table, column, revision, reason in SENTINEL_REVISIONS:
        if not has_table(inspector, table):
            continue
        if column:
            if not has_column(inspector, table, column):
                continue
        found.append((revision, reason))
    return found


def detect_applied_revision(inspector) -> Tuple[str | None, str | None]:
    found = detect_applied_revisions(inspector)
    if not found:
        return None, None
    return found[0]


def has_any_tables(inspector) -> bool:
    return bool(inspector.get_table_names())


def get_current_revision(inspector, connection) -> str | None:
    if not has_table(inspector, "alembic_version"):
        return None
    result = connection.execute(text("SELECT version_num FROM alembic_version"))
    row = result.fetchone()
    return row[0] if row else None


def build_revision_order(script: ScriptDirectory) -> dict[str, int]:
    revisions = list(script.walk_revisions(base="base", head="heads"))
    revisions.reverse()
    return {rev.revision: idx for idx, rev in enumerate(revisions)}


def select_highest_revision(
    found: Iterable[Tuple[str, str]],
    order_map: dict[str, int],
) -> Tuple[str | None, str | None]:
    best_revision = None
    best_reason = None
    best_index = -1
    for revision, reason in found:
        index = order_map.get(revision)
        if index is None:
            continue
        if index > best_index:
            best_revision = revision
            best_reason = reason
            best_index = index
    return best_revision, best_reason


def stamp_revision(revision: str) -> None:
    print(f"BOOTSTRAP: stamping alembic_version to {revision}", flush=True)
    run_alembic("stamp", revision)


def upgrade_head_with_retry(run_drift: callable) -> None:
    try:
        run_alembic("upgrade", "head")
        return
    except subprocess.CalledProcessError as exc:
        print(
            f"BOOTSTRAP: upgrade head failed ({exc}); attempting drift reconciliation and retry",
            flush=True,
        )
        run_drift()
        try:
            run_alembic("upgrade", "head")
            return
        except subprocess.CalledProcessError as retry_exc:
            raise SystemExit(
                "BOOTSTRAP: upgrade head failed after retry; manual intervention required"
            ) from retry_exc


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
    order_map = build_revision_order(script)

    engine = create_engine(database_url)
    try:
        def evaluate_drift(log: bool = False) -> tuple[str | None, str | None, bool]:
            with engine.connect() as connection:
                inspector = inspect(connection)
                current_revision = get_current_revision(inspector, connection)
                if current_revision:
                    try:
                        script.get_revision(current_revision)
                    except ResolutionError:
                        print(
                            f"BOOTSTRAP: alembic_version {current_revision} not found in migration history",
                            flush=True,
                        )
                        raise SystemExit(
                            "BOOTSTRAP: alembic_version exists but does not match known revisions; "
                            "manual intervention required"
                        )
                found = detect_applied_revisions(inspector)
                implied_revision, reason = select_highest_revision(found, order_map)
                has_tables = has_any_tables(inspector)

            if log:
                if current_revision:
                    print(f"BOOTSTRAP: detected alembic_version {current_revision}", flush=True)
                else:
                    print("BOOTSTRAP: alembic_version table not found", flush=True)
                if found:
                    print("BOOTSTRAP: sentinel checks found:", flush=True)
                    for revision, reason_item in found:
                        print(f" - {reason_item} -> {revision}", flush=True)
                else:
                    print("BOOTSTRAP: sentinel checks found none", flush=True)
                if implied_revision:
                    print(
                        f"BOOTSTRAP: highest implied revision {implied_revision} from {reason}",
                        flush=True,
                    )
            return current_revision, implied_revision, has_tables

        def run_drift_reconcile() -> None:
            current_revision, implied_revision, _ = evaluate_drift(log=True)
            if implied_revision is None:
                return
            current_index = order_map.get(current_revision) if current_revision else None
            implied_index = order_map.get(implied_revision)
            if implied_index is None:
                return
            if current_index is None or current_index < implied_index:
                stamp_revision(implied_revision)

        current_revision, implied_revision, has_tables = evaluate_drift(log=True)
        if not current_revision:
            target_revision = implied_revision or "base"
            print(
                f"BOOTSTRAP: alembic_version missing; stamping to {target_revision}",
                flush=True,
            )
            stamp_revision(target_revision)
        elif implied_revision:
            current_index = order_map.get(current_revision)
            implied_index = order_map.get(implied_revision)
            if implied_index is not None and (current_index is None or current_index < implied_index):
                stamp_revision(implied_revision)

        if not has_tables and not current_revision:
            print("BOOTSTRAP: fresh database detected; running upgrade", flush=True)
            upgrade_head_with_retry(run_drift_reconcile)
            return

        print("BOOTSTRAP: running alembic upgrade head", flush=True)
        upgrade_head_with_retry(run_drift_reconcile)
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
