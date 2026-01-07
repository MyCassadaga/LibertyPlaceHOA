import os
import subprocess
from sqlalchemy import create_engine, inspect

ALEMBIC_CONFIG = "backend/alembic.ini"

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

def main() -> None:
    db = os.environ["DATABASE_URL"].strip().strip("'").strip('"')

    # If DB already has the multi-role join table, we are at least at "0008".
    # Stamp to 0008 so Alembic doesn't try to recreate it.
    if has_table(db, "user_roles"):
        print("BOOTSTRAP: user_roles exists -> stamping 0008_multi_role_accounts", flush=True)
        run_alembic("stamp", "0008_multi_role_accounts")
    else:
        # Otherwise, at least stamp baseline if alembic_version missing
        if not has_table(db, "alembic_version"):
            print("BOOTSTRAP: alembic_version missing -> stamping 0001_initial", flush=True)
            run_alembic("stamp", "0001_initial")

    run_alembic("upgrade", "head")

if __name__ == "__main__":
    main()

