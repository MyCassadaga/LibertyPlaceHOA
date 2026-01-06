from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache


def _resolve_git_sha() -> str:
    sha = os.getenv("GIT_SHA") or os.getenv("RENDER_GIT_COMMIT")
    if sha:
        return sha
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def _resolve_build_time() -> str:
    return os.getenv("BUILD_TIME", datetime.now(timezone.utc).isoformat())


def _resolve_env() -> str:
    return os.getenv("APP_ENV", os.getenv("ENV", "unknown"))


@lru_cache
def get_version_info() -> dict[str, str]:
    return {
        "gitSha": _resolve_git_sha(),
        "buildTime": _resolve_build_time(),
        "env": _resolve_env(),
    }
