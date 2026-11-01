"""Portable, verifiable backups of user-owned PubPartner relationship data."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

BACKUP_FORMAT = "PubPartnerFriendBackup.v1"
_ALLOWED_ROOTS = ("profiles", "guidance", "relationship", "receipts", "sessions", "verbatim")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_friend_backup(data_dir: Path | str, *, user_id: str = "anon", friend_id: str = "craig") -> Dict[str, Any]:
    data_dir = Path(data_dir)
    root = data_dir / "pubpartner"
    out_dir = root / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_user = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(user_id or "anon"))[:80]
    safe_friend = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(friend_id or "friend"))[:80]
    filename = f"PubPartner_Friend_Backup_{safe_user}_{safe_friend}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.zip"
    target = out_dir / filename

    candidates: List[Path] = []
    for name in _ALLOWED_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
            # User filtering is best-effort because legacy stores use multiple
            # layouts. Profile/provider defaults are intentionally included;
            # secrets and BYOK data are outside the allowed roots.
            rel_text = rel.as_posix()
            if name in {"relationship", "verbatim"} and safe_user not in rel_text:
                continue
            candidates.append(path)

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
            "PubPartner friend backup\n\nThis archive contains user-owned profiles, guidance, relationship records, receipts, sessions, and exact-source custody records. It does not contain API keys or runtime secrets. Restore support should verify every manifest hash before writing data.\n",
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
