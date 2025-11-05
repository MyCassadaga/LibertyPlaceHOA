import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("backups/sqlite")


def _resolve_sqlite_path(database_url: str) -> Optional[Path]:
    if not database_url.startswith("sqlite:///"):
        return None
    return Path(database_url.replace("sqlite:///", "", 1))


def perform_sqlite_backup(destination_dir: Path | None = None) -> Optional[Path]:
    """Create a timestamped backup of the configured SQLite database."""
    db_path = _resolve_sqlite_path(settings.database_url)
    if db_path is None:
        logger.info("Database URL is not SQLite; skipping backup.")
        return None

    if not db_path.exists():
        logger.warning("SQLite database file %s does not exist; skipping backup.", db_path)
        return None

    target_dir = destination_dir or BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = target_dir / f"{db_path.stem}_{timestamp}.sqlite3"

    logger.info("Backing up SQLite database %s -> %s", db_path, backup_path)

    source = sqlite3.connect(str(db_path))
    dest = sqlite3.connect(str(backup_path))

    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()

    return backup_path
