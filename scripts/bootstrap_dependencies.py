#!/usr/bin/env python3
"""Install PubPartner dependencies inside the active interpreter environment.

The Windows launchers call this with ``.venv/Scripts/python.exe`` so the user's
global Python environment is not modified. Presence and declared version ranges
are both checked before deciding that setup is complete.
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import List

REQUIRED_IMPORTS = (
    "fastapi",
    "uvicorn",
    "starlette",
    "pydantic",
    "httpx",
    "multipart",
    "aiosqlite",
    "jinja2",
    "bcrypt",
)


def missing_modules() -> list[str]:
    return [name for name in REQUIRED_IMPORTS if importlib.util.find_spec(name) is None]


def requirement_problems(requirements: Path) -> List[str]:
    try:
        from packaging.requirements import Requirement
    except Exception:
        # pip environments normally include packaging. Missing packaging should
        # not falsely declare success; force the ordinary install/verify path.
        return ["packaging metadata unavailable"]

    problems: List[str] = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            req = Requirement(line)
        except Exception:
            continue
        if req.marker and not req.marker.evaluate():
            continue
        try:
            installed = metadata.version(req.name)
        except metadata.PackageNotFoundError:
            problems.append(f"{req.name}: not installed")
            continue
        if req.specifier and installed not in req.specifier:
            problems.append(f"{req.name}: installed {installed}, requires {req.specifier}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Check/install PubPartner Python dependencies")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    requirements = root / "requirements.txt"

    missing = missing_modules()
    problems = requirement_problems(requirements)
    if not missing and not problems:
        print("PubPartner dependencies and declared versions are ready in the isolated environment.")
        return 0

    if missing:
        print("Missing Python modules: " + ", ".join(missing))
    if problems:
        print("Dependency version checks requiring repair:")
        for problem in problems:
            print("  - " + problem)
    if args.check_only:
        return 2

    print("Installing or repairing PubPartner dependencies inside the active environment...")
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        print("Dependency installation failed. See the messages above.", file=sys.stderr)
        return completed.returncode or 1

    still_missing = missing_modules()
    still_problematic = requirement_problems(requirements)
    if still_missing or still_problematic:
        print("Dependency verification still failed after installation.", file=sys.stderr)
        for item in [*still_missing, *still_problematic]:
            print("  - " + item, file=sys.stderr)
        return 3
    print("PubPartner dependencies installed and version-verified successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
