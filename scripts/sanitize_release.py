#!/usr/bin/env python3
"""Remove generated runtime state and secrets from a PubPartner release tree.

Run this only on a release copy, never on a user's live data directory.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

RUNTIME_FILES = (
    "data/byok/secure/master.key",
    "data/secure/master.key",
    "data/governance/governance.db",
    "data/system/system_memory.db",
    "data/users.db",
    "data/vault/vault.db",
    "data/pubpartner/secure/jwt_secret.txt",
    "data/pubpartner/preflight_latest.json",
    "data/emergency_bridge/bridge_control.json",
    "data/logs/production.jsonl",
    "data/global/performance_profile.json",
    "data/global/production.json",
    "data/global/dm_requests.sqlite3",
    "data/conversation_archive/conversations.sqlite3",
    "data/memory/pubcast_memory.db",
    "data/memory_snapshot.json",
    "data/writers_room/documents.sqlite3",
    "pubpartner_windows_launcher.log",
)
RUNTIME_DIRS = (
    "data/recordings/test_session",
    "data/alex",
    "data/blackbox",
    "data/dressing_room_security",
    "data/pub_partner_chat",
    "data/sessions",
    "data/pubpartner/backups",
    "data/pubpartner/profiles/users",
    "data/pub_manager",
    "data/black_box",
    "data/emergency_saves",
    "data/alex/target-live",
    "data/alex_bridge",
)
KEEP_DIRS = (
    "data/byok/secure",
    "data/secure",
    "data/alex",
    "data/blackbox",
    "data/conversation_archive",
    "data/dressing_room_security",
    "data/pub_partner_chat",
    "data/sessions",
    "data/memory",
    "data/writers_room",
    "data/global",
    "data/governance",
    "data/system",
    "data/vault",
    "data/logs",
    "data/emergency_bridge/commands",
    "data/emergency_bridge/responses",
    "data/pubpartner/guidance",
    "data/pubpartner/receipts",
    "data/pubpartner/sessions",
    "data/pubpartner/verbatim",
    "data/pubpartner/relationship",
    "data/pubpartner/authority",
    "data/pubpartner/secure",
    "data/pubpartner/backups",
    "data/pubpartner/profiles/users",
    "data/pub_manager/authority",
    "data/black_box",
    "data/emergency_saves",
    "data/alex_bridge",
)


def sanitize(root: Path) -> list[str]:
    removed: list[str] = []
    for rel in RUNTIME_FILES:
        path = root / rel
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(rel)
    for rel in RUNTIME_DIRS:
        path = root / rel
        if path.exists():
            shutil.rmtree(path)
            removed.append(rel + "/")
    command_dir = root / "data/emergency_bridge/commands"
    if command_dir.exists():
        for path in command_dir.glob("*.json"):
            path.unlink()
            removed.append(str(path.relative_to(root)))
    for cache in list(root.rglob("__pycache__")) + list(root.rglob(".pytest_cache")):
        if cache.is_dir():
            shutil.rmtree(cache)
            removed.append(str(cache.relative_to(root)) + "/")
    for pyc in root.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
        removed.append(str(pyc.relative_to(root)))
    for rel in KEEP_DIRS:
        folder = root / rel
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ".gitkeep").touch(exist_ok=True)
    return sorted(set(removed))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    removed = sanitize(root)
    print(f"Sanitized release tree: {root}")
    print(f"Removed {len(removed)} generated items.")
    for item in removed:
        print("- " + item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
