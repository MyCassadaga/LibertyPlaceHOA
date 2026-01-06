import os
import subprocess

from sqlalchemy import create_engine, inspect


ALEMBIC_CONFIG = "backend/alembic.ini"
BASE_REVISION = "0001_initial"


def _run_alembic(args: list[str]) -> None:
    command = ["alembic", "-c", ALEMBIC_CONFIG, *args]
    subprocess.run(command, check=True)


def _alembic_version_exists(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        return inspector.has_table("alembic_version")
    finally:
        engine.dispose()


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to bootstrap migrations")

    if not _alembic_version_exists(database_url):
        _run_alembic(["stamp", BASE_REVISION])

    _run_alembic(["upgrade", "head"])


if __name__ == "__main__":
    main()
