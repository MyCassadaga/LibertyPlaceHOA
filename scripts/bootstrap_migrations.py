import os
import subprocess
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from sqlalchemy import create_engine, inspect, text

ALEMBIC_CONFIG = "backend/alembic.ini"
REVISION_BASELINE = "0001_initial"
REVISION_MULTI_ROLE = "0008_multi_role_accounts"
REVISION_BUDGETS = "7a73908faa2a_budget_and_reserve"

def run_alembic(*args: str) -> None:
    cmd = ["alembic", "-c", ALEMBIC_CONFIG, *args]
    print("RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def has_table(database_url: str, name: str) -> bool:
    engine = create_engine(database_url)
    try:
        return inspect(engine).has_table(name)
    finally:
        engine.dispose()

def get_current_revision(database_url: str) -> str | None:
    if not has_table(database_url, "alembic_version"):
        return None
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else None
    finally:
        engine.dispose()

def is_revision_at_least(script: ScriptDirectory, current: str | None, target: str) -> bool:
    if current is None:
        return False
    if current == target:
        return True
    try:
        for revision in script.iterate_revisions(current, target):
            if revision.revision == target:
                return True
    except ResolutionError:
        print(
            f"BOOTSTRAP: current revision {current} not found in migration history; treating as unknown",
            flush=True,
        )
        return False
    return False

def main() -> None:
    db = os.environ["DATABASE_URL"].strip().strip("'").strip('"')
    if db.startswith("psql "):
        db = db[5:].strip().strip("'").strip('"')
    config = Config(ALEMBIC_CONFIG)
    script = ScriptDirectory.from_config(config)

    target_revision = None
    target_reason = None
    if has_table(db, "budgets"):
        target_revision = REVISION_BUDGETS
        target_reason = "budgets exists"
    elif has_table(db, "user_roles"):
        target_revision = REVISION_MULTI_ROLE
        target_reason = "user_roles exists"
    elif not has_table(db, "alembic_version"):
        target_revision = REVISION_BASELINE
        target_reason = "alembic_version missing"

    current_revision = get_current_revision(db)
    current_revision_valid = False
    if current_revision:
        try:
            current_revision_valid = script.get_revision(current_revision) is not None
        except ResolutionError:
            current_revision_valid = False

    if current_revision and current_revision_valid:
        print(
            f"BOOTSTRAP: alembic_version present ({current_revision}); skipping stamping",
            flush=True,
        )
    elif target_revision:
        if script.get_revision(target_revision) is None:
            print(
                f"BOOTSTRAP: target revision {target_revision} not found; skipping stamping",
                flush=True,
            )
        elif is_revision_at_least(script, current_revision, target_revision):
            print(
                f"BOOTSTRAP: current revision {current_revision} already at/after {target_revision}; skip stamping",
                flush=True,
            )
        else:
            print(
                f"BOOTSTRAP: {target_reason} -> stamping {target_revision}",
                flush=True,
            )
            run_alembic("stamp", target_revision)
    else:
        if current_revision and not current_revision_valid:
            print(
                f"BOOTSTRAP: alembic_version {current_revision} not found and no target tables detected; skipping stamping",
                flush=True,
            )
        else:
            print(
                "BOOTSTRAP: no stamping needed (alembic_version present and no target tables detected)",
                flush=True,
            )

    run_alembic("upgrade", "head")

if __name__ == "__main__":
    main()
