#!/usr/bin/env python3
"""Helper to run migrations, backend, and frontend dev servers together.

Usage:
    python scripts/start_dev.py
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Iterable, Tuple

try:
    import shutil
except ImportError:  # pragma: no cover
    shutil = None  # type: ignore


ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
VENV_DIR = ROOT / ".venv"

if sys.platform == "win32":
    VENV_BIN = VENV_DIR / "Scripts"
else:
    VENV_BIN = VENV_DIR / "bin"

DEFAULT_PORTS = {
    "backend": os.environ.get("HOA_BACKEND_PORT", "8001"),
    "frontend": os.environ.get("HOA_FRONTEND_PORT", "5174"),
}


def _find_executable(name: str) -> Path | None:
    """Look inside the venv first, fall back to PATH."""
    candidates: Iterable[Path] = ()
    if VENV_BIN.exists():
        candidates = (
            VENV_BIN / name,
            VENV_BIN / f"{name}.exe",
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if shutil is None:
        return None
    resolved = shutil.which(name)
    return Path(resolved) if resolved else None


async def _run_command(
    name: str,
    cmd: Tuple[str, ...],
    cwd: Path,
    env: dict[str, str],
) -> asyncio.subprocess.Process:
    print(f"[launcher] starting {name}: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def _reader() -> None:
        if process.stdout is None:
            return
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="ignore").rstrip()
            print(f"[{name}] {line}")

    asyncio.create_task(_reader())
    return process


async def _run_alembic(alembic_exe: Path, env: dict[str, str]) -> None:
    print("[launcher] applying database migrations...")
    process = await asyncio.create_subprocess_exec(
        str(alembic_exe),
        "-c",
        "backend/alembic.ini",
        "upgrade",
        "head",
        cwd=str(ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode(errors="ignore") if stdout else ""
    if output:
        print(output.strip())
    if process.returncode not in (0, None):
        raise SystemExit(process.returncode)


async def main() -> None:
    backend_port = DEFAULT_PORTS["backend"]
    frontend_port = DEFAULT_PORTS["frontend"]

    uvicorn_exe = _find_executable("uvicorn")
    alembic_exe = _find_executable("alembic")
    npm_exe = _find_executable("npm") or (_find_executable("npm.cmd") if sys.platform == "win32" else None)

    missing = [
        ("uvicorn", uvicorn_exe),
        ("alembic", alembic_exe),
        ("npm", npm_exe),
    ]
    missing_bins = [name for name, path in missing if path is None]
    if missing_bins:
        formatted = ", ".join(missing_bins)
        raise SystemExit(f"Missing required executables: {formatted}. Install dependencies and try again.")

    # Shared environment so imports resolve when running Alembic and uvicorn
    base_env = os.environ.copy()
    base_env.setdefault("PYTHONPATH", str(ROOT))

    if alembic_exe:
        await _run_alembic(alembic_exe, base_env)

    backend_env = base_env.copy()
    backend_env.setdefault("PORT", backend_port)

    backend_cmd = (
        str(uvicorn_exe),
        "backend.main:app",
        "--reload",
        "--port",
        backend_port,
        "--log-level",
        "info",
    )

    frontend_env = base_env.copy()
    frontend_env.setdefault("PORT", frontend_port)
    frontend_cmd = (
        str(npm_exe),
        "run",
        "dev",
        "--",
        "--host",
        "--port",
        frontend_port,
    )

    processes: list[asyncio.subprocess.Process] = []
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:  # pragma: no cover
            pass

    try:
        processes.append(await _run_command("backend", backend_cmd, BACKEND_DIR, backend_env))
        processes.append(await _run_command("frontend", frontend_cmd, FRONTEND_DIR, frontend_env))
        print("[launcher] backend on http://127.0.0.1:%s" % backend_port)
        print("[launcher] frontend on http://127.0.0.1:%s" % frontend_port)
        print("[launcher] press Ctrl+C to stop both services.")
        await stop_event.wait()
    finally:
        print("[launcher] shutting down...")
        for proc in processes:
            if proc.returncode is None:
                proc.terminate()
        await asyncio.gather(*(proc.wait() for proc in processes), return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[launcher] interrupted by user.")
