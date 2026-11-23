"""Portable, verifiable backups of user-owned PubPartner relationship data."""
from __future__ import annotations

import hashlib
import re
import json
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

BACKUP_FORMAT = "PubPartnerFriendBackup.v1"
_ALLOWED_ROOTS = ("profiles", "guidance", "relationship", "receipts", "sessions", "verbatim", "calibration")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(value: str, limit: int = 120) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(value or "anon"))[:limit]


def _record_owner_matches(path: Path, user_id: str) -> bool:
    """Require self-identification for receipt and turn logs; filenames alone
    cannot disambiguate underscores in different user IDs.
    """
    try:
        if path.name.endswith("_turns.jsonl"):
            # Turn records lack a guaranteed top-level user ID. They belong to
            # a session identified by the paired state file.
            state_path = path.with_name(path.name.removesuffix("_turns.jsonl") + ".json")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            return state.get("user_id") == user_id
        if path.suffix == ".jsonl":
            any_rows = False
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                any_rows = True
                if json.loads(line).get("user_id") != user_id:
                    return False
            return any_rows
        return json.loads(path.read_text(encoding="utf-8")).get("user_id") == user_id
    except (ValueError, OSError, AttributeError, TypeError):
        return False


def _eligible_backup_files(root: Path, *, user_id: str, friend_id: str) -> List[Path]:
    """Select by canonical path ownership, never fuzzy string containment.

    Ambiguous or malformed legacy files are excluded rather than risk a
    cross-user or cross-partner backup. Provider credentials, wallets, and
    other unscoped state never enter this ZIP.
    """
    su, sf = _slug(user_id), _slug(friend_id)
    chosen: List[Path] = []

    def include(path: Path):
        if path.is_file() and not path.is_symlink():
            chosen.append(path)

    for leaf in (root / "profiles" / "friends" / f"{sf}.json",
                 root / "profiles" / "users" / f"{su}.json",
                 root / "guidance" / f"{su}.jsonl"):
        include(leaf)
    for folder in (root / "relationship" / su / sf,
                   root / "verbatim" / su,
                   root / "calibration" / su):
        if folder.exists() and not folder.is_symlink():
            for path in folder.rglob("*"):
                if any(parent.is_symlink() for parent in path.parents if parent != root):
                    continue
                include(path)
    for folder in (root / "receipts", root / "sessions"):
        if not folder.exists():
            continue
        for path in folder.glob(f"{su}_*"):
            if not path.is_file() or path.is_symlink():
                continue
            if folder.name == "sessions" and path.name.endswith("_turns.jsonl"):
                # The matching saved session state must assert the owner.
                if _record_owner_matches(path, user_id):
                    include(path)
            elif _record_owner_matches(path, user_id):
                include(path)
    return sorted(set(chosen))


def create_friend_backup(data_dir: Path | str, *, user_id: str = "anon", friend_id: str = "craig") -> Dict[str, Any]:
    data_dir = Path(data_dir)
    root = data_dir / "pubpartner"
    out_dir = root / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_user = _slug(user_id, 80)
    safe_friend = _slug(friend_id, 80)
    filename = f"PubPartner_Friend_Backup_{safe_user}_{safe_friend}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.zip"
    target = out_dir / filename

    candidates = _eligible_backup_files(root, user_id=user_id, friend_id=friend_id)

    manifest = {
        "format": BACKUP_FORMAT,
        "created_at": time.time(),
        "user_id": user_id,
        "friend_id": friend_id,
        "contains_secrets": False,
        "roots": list(_ALLOWED_ROOTS),
        "files": [],
    }
    for path in sorted(set(candidates)):
        rel = path.relative_to(root).as_posix()
        manifest["files"].append({"path": rel, "size": path.stat().st_size, "sha256": _sha(path)})

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("PUBPARTNER_BACKUP_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(
            "README_RESTORE.txt",
            "PubPartner friend backup\n\nThis archive contains owner-scoped partner profiles, guidance, relationship records, conversation sources, calibration records, and verified session files. It excludes other users, provider credentials, Wallet custody, and runtime secrets. Verify manifest hashes before recovery.\n",
        )
        for path in sorted(set(candidates)):
            zf.write(path, arcname=f"pubpartner/{path.relative_to(root).as_posix()}")

    return {
        "ok": True,
        "format": BACKUP_FORMAT,
        "filename": filename,
        "path": str(target),
        "file_count": len(manifest["files"]),
        "size": target.stat().st_size,
        "sha256": _sha(target),
        "download_url": f"/api/pubpartner/backups/{filename}",
        "contains_secrets": False,
    }


def verify_friend_backup(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"ok": False, "error": "backup not found"}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            manifest = json.loads(zf.read("PUBPARTNER_BACKUP_MANIFEST.json").decode("utf-8"))
            if manifest.get("format") != BACKUP_FORMAT:
                return {"ok": False, "error": "unsupported backup format"}
            for row in manifest.get("files", []):
                arc = "pubpartner/" + str(row.get("path") or "")
                data = zf.read(arc)
                digest = hashlib.sha256(data).hexdigest()
                if digest != row.get("sha256"):
                    return {"ok": False, "error": "hash mismatch", "path": row.get("path")}
            return {"ok": True, "files": len(manifest.get("files", [])), "manifest": manifest}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


__all__ = ["create_friend_backup", "verify_friend_backup", "BACKUP_FORMAT"]
