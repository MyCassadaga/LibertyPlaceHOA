#!/usr/bin/env python3
"""Generate a high-signal repository overview in Markdown."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

DEFAULT_DEPTH = 4
DEFAULT_OUTPUT = "docs/REPO_TOUR.md"

DEFAULT_EXCLUDES = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".eggs",
    ".tox",
}

SECRET_GLOBS = (
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "*.crt",
    "*.cer",
    "*.der",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.pgpass",
)

DOC_EXTRA_FILES = (
    "README",
    "README.md",
    "README.rst",
    "README.txt",
    "CONTRIBUTING",
    "CONTRIBUTING.md",
    "RUNBOOK",
    "RUNBOOK.md",
    "DEPLOYMENT",
    "DEPLOYMENT.md",
    "CHANGELOG",
    "CHANGELOG.md",
)

ENTRYPOINT_PATTERNS = (
    "main.py",
    "app/main.py",
    "server.ts",
    "server.js",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "Dockerfile",
    "render.yaml",
    "vercel.json",
    "wrangler.toml",
)

PROVIDER_KEYWORDS = (
    "Render",
    "Vercel",
    "Cloudflare",
    "Neon",
    "Google Workspace",
    "Gmail",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate repo intake documentation.")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help="Output markdown path")
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help="Depth for repo tree output (default: 4)",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated glob patterns to exclude",
    )
    return parser.parse_args()


def matches_any(path: Path, patterns: Iterable[str]) -> bool:
    rel_path = path.as_posix()
    name = path.name
    for pattern in patterns:
        if not pattern:
            continue
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def is_secret(path: Path) -> bool:
    name = path.name
    if name == ".env":
        return True
    if name.startswith(".env.") and name not in {".env.example", ".env.template"}:
        return True
    if name.startswith(".env.example"):
        return False
    return matches_any(path, SECRET_GLOBS)


def should_skip(path: Path, excludes: Iterable[str]) -> bool:
    if any(part in DEFAULT_EXCLUDES for part in path.parts):
        return True
    return matches_any(path, excludes) or is_secret(path)


def build_tree(root: Path, depth: int, excludes: Iterable[str]) -> List[str]:
    lines: List[str] = []

    def walk(current: Path, prefix: str, remaining: int) -> None:
        if remaining < 0:
            return
        entries = sorted(
            [p for p in current.iterdir() if not should_skip(p, excludes)],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
        count = len(entries)
        for idx, entry in enumerate(entries):
            connector = "└── " if idx == count - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if idx == count - 1 else "│   "
                walk(entry, prefix + extension, remaining - 1)

    walk(root, "", depth)
    return lines


def find_dirs(root: Path, base: str) -> List[str]:
    base_path = root / base
    if not base_path.exists() or not base_path.is_dir():
        return []
    subdirs = sorted([p.name for p in base_path.iterdir() if p.is_dir()])
    return subdirs


def find_entrypoints(root: Path, excludes: Iterable[str]) -> List[str]:
    found: List[str] = []
    for pattern in ENTRYPOINT_PATTERNS:
        for path in root.rglob(pattern):
            if should_skip(path, excludes):
                continue
            if path.is_file():
                found.append(path.relative_to(root).as_posix())
    return sorted(set(found))


def read_first_line(path: Path) -> str:
    if is_secret(path):
        return "(ignored secret-like file)"
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    return stripped
                return stripped
    except OSError:
        return "(unreadable)"
    return "(empty)"


def gather_docs(root: Path, excludes: Iterable[str]) -> List[Tuple[str, str]]:
    docs: List[Tuple[str, str]] = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        for path in sorted(docs_dir.rglob("*.md")):
            if should_skip(path, excludes) or is_secret(path):
                continue
            rel = path.relative_to(root).as_posix()
            docs.append((rel, read_first_line(path)))
    for name in DOC_EXTRA_FILES:
        path = root / name
        if path.exists() and path.is_file():
            if should_skip(path, excludes) or is_secret(path):
                continue
            docs.append((path.relative_to(root).as_posix(), read_first_line(path)))
    return docs


def find_env_surface(root: Path, excludes: Iterable[str]) -> List[str]:
    entries: List[str] = []
    for path in root.rglob(".env.example*"):
        if should_skip(path, excludes) or is_secret(path):
            continue
        entries.append(path.relative_to(root).as_posix())
    for path in root.rglob(".env.template"):
        if should_skip(path, excludes) or is_secret(path):
            continue
        entries.append(path.relative_to(root).as_posix())
    for path in root.rglob("alembic.ini"):
        if should_skip(path, excludes):
            continue
        entries.append(path.relative_to(root).as_posix())
    for path in root.rglob("migrations"):
        if should_skip(path, excludes):
            continue
        if path.is_dir():
            entries.append(path.relative_to(root).as_posix() + "/")
    for path in root.rglob("settings*"):
        if should_skip(path, excludes) or path.is_dir():
            continue
        entries.append(path.relative_to(root).as_posix())
    for path in root.rglob("config"):
        if should_skip(path, excludes):
            continue
        if path.is_dir():
            entries.append(path.relative_to(root).as_posix() + "/")
    ci_candidates = [
        ".github/workflows",
        ".gitlab-ci.yml",
        ".circleci",
        "azure-pipelines.yml",
        "buildkite.yml",
        "render.yaml",
    ]
    for candidate in ci_candidates:
        path = root / candidate
        if path.exists():
            entries.append(candidate + ("/" if path.is_dir() else ""))
    return sorted(set(entries))


def find_package_scripts(root: Path, excludes: Iterable[str]) -> List[Tuple[str, dict]]:
    packages: List[Tuple[str, dict]] = []
    for path in sorted(root.rglob("package.json")):
        if should_skip(path, excludes):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scripts = data.get("scripts") or {}
        if scripts:
            packages.append((path.relative_to(root).as_posix(), scripts))
    return packages


def find_python_entrypoints(root: Path, excludes: Iterable[str]) -> List[str]:
    candidates = [
        "main.py",
        "app/main.py",
        "backend/main.py",
        "manage.py",
        "scripts/start_dev.py",
        "scripts/bootstrap_migrations.py",
    ]
    found: List[str] = []
    for candidate in candidates:
        path = root / candidate
        if path.exists() and path.is_file() and not should_skip(path, excludes):
            found.append(candidate)
    return found


def detect_providers_from_docs(
    root: Path,
    excludes: Iterable[str],
    ignore_paths: Optional[Iterable[Path]] = None,
) -> List[Tuple[str, str]]:
    docs_paths = [
        root / "README.md",
        root / "docs",
    ]
    ignore_set = {path.resolve() for path in (ignore_paths or [])}
    matches: List[Tuple[str, str]] = []
    for base in docs_paths:
        if not base.exists():
            continue
        if base.is_file():
            paths = [base]
        else:
            paths = list(base.rglob("*.md"))
        for path in sorted(paths):
            if should_skip(path, excludes) or is_secret(path):
                continue
            if path.resolve() in ignore_set:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for keyword in PROVIDER_KEYWORDS:
                if keyword in content:
                    matches.append((keyword, path.relative_to(root).as_posix()))
    return sorted(set(matches))


def format_list(items: Sequence[str]) -> str:
    if not items:
        return "- (none found)"
    return "\n".join(f"- {item}" for item in items)


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    extra_excludes = [
        item.strip()
        for item in args.exclude.split(",")
        if item.strip()
    ]

    output_path = Path(args.out)

    tree_lines = build_tree(root, args.depth, extra_excludes)
    entrypoints = find_entrypoints(root, extra_excludes)
    docs = gather_docs(root, extra_excludes)
    env_surface = find_env_surface(root, extra_excludes)
    package_scripts = find_package_scripts(root, extra_excludes)
    python_entrypoints = find_python_entrypoints(root, extra_excludes)
    providers = detect_providers_from_docs(
        root,
        extra_excludes,
        ignore_paths=[output_path],
    )

    app_groups = {
        "apps": find_dirs(root, "apps"),
        "services": find_dirs(root, "services"),
        "packages": find_dirs(root, "packages"),
        "backend": ["backend"] if (root / "backend").is_dir() else [],
        "frontend": ["frontend"] if (root / "frontend").is_dir() else [],
    }

    lines: List[str] = []
    lines.append("# Repository Tour")
    lines.append("")
    lines.append("This document is generated by `scripts/repo_intake.py`.")
    lines.append("")
    lines.append("## Repo tree (depth-limited)")
    lines.append("```")
    lines.append(".")
    lines.extend(tree_lines)
    lines.append("```")
    lines.append("")

    lines.append("## Detected apps/services/packages")
    for key, values in app_groups.items():
        label = key.capitalize()
        lines.append(f"- **{label}**: {', '.join(values) if values else '(none found)'}")
    lines.append("")

    lines.append("## Key entry points (best-effort)")
    lines.append(format_list(entrypoints))
    lines.append("")

    lines.append("## Documentation inventory")
    if docs:
        for path, excerpt in docs:
            lines.append(f"- `{path}` — {excerpt}")
    else:
        lines.append("- (none found)")
    lines.append("")

    lines.append("## Environment/config surface area")
    lines.append(format_list(env_surface))
    lines.append("")

    lines.append("## How to run locally")
    lines.append("### Package scripts")
    if package_scripts:
        for pkg_path, scripts in package_scripts:
            lines.append(f"- `{pkg_path}`")
            for name, cmd in scripts.items():
                lines.append(f"  - `{name}`: `{cmd}`")
    else:
        lines.append("- (no package.json scripts found)")

    lines.append("")
    lines.append("### Python entrypoints")
    if python_entrypoints:
        lines.append(format_list(python_entrypoints))
        lines.append("")
        lines.append("If commands are unclear, consult README or add them here once confirmed.")
    else:
        lines.append("- (no obvious python entrypoints found)")
    lines.append("")

    lines.append("## How it deploys (evidence only)")
    if providers:
        for provider, source in providers:
            lines.append(f"- `{provider}` referenced in `{source}`")
    else:
        lines.append("- (no provider references found in docs)")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
