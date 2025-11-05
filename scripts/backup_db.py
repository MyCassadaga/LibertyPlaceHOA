#!/usr/bin/env python3
"""Utility to dump the configured SQLite database into backups/sqlite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.backup import BACKUP_DIR, perform_sqlite_backup  # noqa: E402


def main() -> None:
    backup_path = perform_sqlite_backup()
    if backup_path:
        print(f"SQLite backup created at {backup_path}")
    else:
        print("No SQLite backup created (non-SQLite database or file missing).")


if __name__ == "__main__":
    main()
