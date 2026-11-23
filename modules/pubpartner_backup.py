"""Portable, verifiable backups of user-owned PubPartner relationship data."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import tempfile
import json
import time
import uuid
import zipfile

from .pubpartner_blackbox_light import PubPartnerBlackboxLight
from pathlib import Path
from typing import Any, Dict, List

BACKUP_FORMAT = "PubPartnerFriendBackup.v1"
_ALLOWED_ROOTS = ("profiles", "guidance", "relationship", "receipts", "sessions", "verbatim", "calibration")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(value: str, limit: int = 120) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "anon")).strip("._-")
    return (cleaned or "anon")[:limit]


def _session_identity(path: Path) -> Dict[str, str]:
    """Resolve the explicit session owner and partner; never trust filename
    prefixes as proof of ownership or character identity.
    """
    if path.name.endswith("_turns.jsonl"):
        path = path.with_name(path.name.removesuffix("_turns.jsonl") + ".json")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        friend = state.get("friend") or {}
        return {"user_id": str(state.get("user_id") or ""),
                "friend_id": str(friend.get("id") or friend.get("friend_id") or "")}
    except (ValueError, OSError, AttributeError, TypeError):
        return {}


def _receipt_matches(path: Path, *, user_id: str, friend_id: str, root: Path) -> bool:
    """Receipts do not carry a friend ID, so only include a chain if its
    exact matching session state belongs to this user and partner.
    """
    prefix = path.name.removesuffix(".jsonl")
    state = root / "sessions" / (prefix + ".json")
    scope = _session_identity(state)
    if scope != {"user_id": user_id, "friend_id": friend_id}:
        return False
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return bool(rows) and all(row.get("user_id") == user_id for row in rows)
    except (ValueError, OSError, TypeError):
        return False


def _session_is_exclusive(path: Path, *, user_id: str, friend_id: str) -> bool:
    """A session is portable as a whole only if every saved turn is this pair.

    Sessions can be reused with another friend, so trusting only the session's
    current friend would leak earlier conversations, sources and receipts.
    """
    if _session_identity(path) != {"user_id": user_id, "friend_id": friend_id}:
        return False
    turns = path.with_name(path.stem + "_turns.jsonl")
    if not turns.exists():
        return True
    if turns.is_symlink():
        return False
    try:
        for line in turns.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            fcp1 = record.get("fcp1") or {}
            if not isinstance(fcp1, dict) or (fcp1.get("f") or {}).get("id") != friend_id:
                return False
        return True
    except (ValueError, OSError, AttributeError, TypeError):
        return False


def _eligible_backup_files(root: Path, *, user_id: str, friend_id: str) -> List[Path]:
    """Choose only precisely attributable owner/partner paths, fail closed."""
    su, sf = _slug(user_id), _slug(friend_id)
    chosen: List[Path] = []

    def include(path: Path) -> None:
        if path.is_file() and not path.is_symlink() and not any(
            parent.is_symlink() for parent in path.parents if parent != root.parent
        ):
            chosen.append(path)

    friend_profile = root / "profiles" / "friends" / f"{sf}.json"
    # Custom cartridge profiles belong to their creator, not to every owner.
    if friend_profile.exists():
        try:
            profile = json.loads(friend_profile.read_text(encoding="utf-8"))
            cartridge = profile.get("cartridge") or {}
            if (profile.get("id") == friend_id and
                friend_id in {"alex", "craig", "friend"} and not cartridge):
                include(friend_profile)
            elif (profile.get("id") == friend_id and isinstance(cartridge, dict) and
                  str(cartridge.get("created_by") or "") == user_id):
                include(friend_profile)
        except (ValueError, OSError, AttributeError, TypeError):
            pass
    user_profile = root / "profiles" / "users" / f"{su}.json"
    if user_profile.is_file() and not user_profile.is_symlink():
        try:
            if json.loads(user_profile.read_text(encoding="utf-8")).get("id") == user_id:
                include(user_profile)
        except (ValueError, OSError, AttributeError, TypeError):
            pass

    # Slug collisions can put another account's lessons under the same folder.
    # Inspect embedded owner/partner in each record before selecting a file.
    pair_dir = root / "relationship" / su / sf
    if pair_dir.is_dir() and not pair_dir.is_symlink():
        lessons = pair_dir / "lessons.json"
        if lessons.is_file() and not lessons.is_symlink():
            try:
                doc = json.loads(lessons.read_text(encoding="utf-8"))
                rows = doc.get("lessons") or []
                if (doc.get("user_id") == user_id and doc.get("friend_id") == friend_id and
                    isinstance(rows, list) and
                    all(isinstance(row, dict) and row.get("user_id") == user_id and
                        row.get("friend_id") == friend_id for row in rows)):
                    include(lessons)
            except (ValueError, OSError, AttributeError, TypeError):
                pass
        encounters = pair_dir / "encounters.jsonl"
        if encounters.is_file() and not encounters.is_symlink():
            try:
                rows = [json.loads(line) for line in encounters.read_text(encoding="utf-8").splitlines()
                        if line.strip()]
                if rows and all(isinstance(row, dict) and row.get("user_id") == user_id and
                                row.get("friend_id") == friend_id for row in rows):
                    include(encounters)
            except (ValueError, OSError, AttributeError, TypeError):
                pass

    sessions_root = root / "sessions"
    matching_states = []
    if sessions_root.is_dir():
        for state in sessions_root.glob(f"{su}_*.json"):
            if not state.is_symlink() and _session_is_exclusive(
                state, user_id=user_id, friend_id=friend_id
            ):
                matching_states.append(state)
                include(state)
                include(state.with_name(state.stem + "_turns.jsonl"))
                receipt = root / "receipts" / (state.stem + ".jsonl")
                if _receipt_matches(receipt, user_id=user_id, friend_id=friend_id, root=root):
                    include(receipt)

    # A complete audit hash chain is only valid for a single-partner session.
    # Do not include a mixed session's raw sources or its audit chain.
    for state in matching_states:
        try:
            state_data = json.loads(state.read_text(encoding="utf-8"))
            session_id = str(state_data["session_id"])
            source_dir = root / "verbatim" / su / _slug(session_id)
            if not source_dir.is_dir() or source_dir.is_symlink():
                continue
            metadata_files = sorted(source_dir.glob("src_*.json"))
            if not metadata_files:
                continue
            safe_sources = []
            for metadata_path in metadata_files:
                source = json.loads(metadata_path.read_text(encoding="utf-8"))
                meta = source.get("metadata") or {}
                if (source.get("user_id") != user_id or
                    source.get("session_id") != session_id or
                    meta.get("friend_id") != friend_id):
                    safe_sources = []
                    break
                raw = metadata_path.with_suffix(".utf8")
                if not raw.is_file() or raw.is_symlink():
                    safe_sources = []
                    break
                safe_sources.extend((metadata_path, raw))
            if safe_sources:
                for path in safe_sources:
                    include(path)
                include(source_dir / "audit_hash_chain.jsonl")
        except (ValueError, OSError, KeyError, AttributeError, TypeError):
            continue

    # Interviews and recorded audio are shared under an owner folder; select
    # only the particular partner's interview ids, never the whole directory.
    calibration = root / "calibration" / su
    if calibration.is_dir() and not calibration.is_symlink():
        for path in calibration.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                if doc.get("user_id") != user_id or doc.get("partner_id") != friend_id:
                    continue
                if doc.get("id") != path.stem:
                    continue
                include(path)
                audio = calibration / "audio" / path.stem
                if audio.is_dir() and not audio.is_symlink():
                    for sample in audio.iterdir():
                        if sample.suffix in {".wav", ".webm", ".m4a", ".ogg"}:
                            include(sample)
            except (ValueError, OSError, AttributeError, TypeError):
                continue

    # The selected cartridge's authored YAML and seed memory belong to this
    # owner. Its live SQLite memory is snapshotted separately while archiving.
    cartridge = root / "cartridges" / sf
    if cartridge.is_dir() and not cartridge.is_symlink():
        appearance = cartridge / "appearance.yaml"
        try:
            import yaml
            meta = yaml.safe_load(appearance.read_text(encoding="utf-8")) or {}
            if str(meta.get("created_by") or "") == user_id:
                for name in ("character.yaml", "voice_profile.yaml",
                             "appearance.yaml", "memories.jsonl"):
                    include(cartridge / name)
        except (ValueError, OSError, AttributeError, TypeError):
            pass

    return sorted(set(chosen))


def _scoped_guidance(root: Path, *, user_id: str, friend_id: str) -> bytes:
    """Project the shared owner guidance file, excluding other partners."""
    path = root / "guidance" / f"{_slug(user_id)}.jsonl"
    if not path.is_file() or path.is_symlink():
        return b""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if (isinstance(row, dict) and row.get("user_id") == user_id and
            row.get("friend_id") in {friend_id, "*"}):
            rows.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return ("\n".join(rows) + "\n").encode("utf-8") if rows else b""


def create_friend_backup(data_dir: Path | str, *, user_id: str = "anon", friend_id: str = "craig") -> Dict[str, Any]:
    """Produce an atomic, verifiable, strictly scoped *working-data* backup.

    It is NOT the paired Iteration Wallet's sealed birth/last-good custody.
    Mixed-partner sessions are excluded rather than silently exported whole.
    """
    data_dir = Path(data_dir)
    root = data_dir / "pubpartner"
    out_dir = root / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_user, safe_friend = _slug(user_id, 80), _slug(friend_id, 80)
    filename = (
        f"PubPartner_Friend_Backup_{safe_user}_{safe_friend}_"
        f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.zip"
    )
    target = out_dir / filename
    temporary_target = out_dir / ("." + filename + ".partial")
    candidates = _eligible_backup_files(root, user_id=user_id, friend_id=friend_id)
    extras: Dict[str, Path] = {}
    warnings = [
        "Not a sealed Iteration Wallet checkpoint; birth/last-good/quarantine custody is separate",
        "Undocked portable state and non-attributable mixed sessions are not included",
        "User-authored text may contain sensitive details even though provider credential stores are excluded",
    ]

    try:
        with tempfile.TemporaryDirectory(prefix="pp_backup_") as staging_dir:
            staging = Path(staging_dir)
            guidance = _scoped_guidance(root, user_id=user_id, friend_id=friend_id)
            if guidance:
                gp = staging / "guidance.jsonl"
                gp.write_bytes(guidance)
                extras[f"guidance/{_slug(user_id)}.jsonl"] = gp

            light_db = data_dir / "conversation_archive" / "pubpartner_light.sqlite3"
            if light_db.exists():
                # The underlying SQLite file spans all users. Never ZIP it whole.
                payload = PubPartnerBlackboxLight(data_dir).export(
                    user_id=user_id, friend_id=friend_id)
                bp = staging / "blackbox_light.json"
                bp.write_text(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")), encoding="utf-8")
                extras["blackbox_light/conversations.json"] = bp

            cartridge = root / "cartridges" / _slug(friend_id)
            yaml_path = cartridge / "appearance.yaml"
            if yaml_path.is_file() and not yaml_path.is_symlink():
                import yaml
                appearance = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                if str(appearance.get("created_by") or "") == user_id:
                    live_db = cartridge / "memories.db"
                    if live_db.is_file() and not live_db.is_symlink():
                        # Take SQLite's transaction-consistent snapshot: raw DB
                        # copy would omit uncheckpointed WAL writes.
                        sqlite_copy = staging / "cartridge_memories.db"
                        source_uri = live_db.resolve().as_uri() + "?mode=ro"
                        with sqlite3.connect(source_uri, uri=True) as original:
                            with sqlite3.connect(sqlite_copy) as destination:
                                original.backup(destination)
                        extras[f"cartridges/{_slug(friend_id)}/memories.db"] = sqlite_copy

            selected = {p.relative_to(root).as_posix(): p for p in candidates}
            if set(selected) & set(extras):
                raise RuntimeError("backup manifest path collision")
            selected.update(extras)
            manifest = {
                "format": BACKUP_FORMAT,
                "created_at": time.time(),
                "user_id": user_id,
                "friend_id": friend_id,
                "scope": "owner_and_partner",
                "backup_kind": "working_data_not_sealed_wallet_custody",
                "contains_secrets": False,
                "roots": sorted({p.split("/", 1)[0] for p in selected}),
                "files": [
                    {"path": rel, "size": path.stat().st_size, "sha256": _sha(path)}
                    for rel, path in sorted(selected.items())
                ],
                "warnings": warnings,
            }
            with zipfile.ZipFile(temporary_target, "w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=9) as zf:
                zf.writestr("PUBPARTNER_BACKUP_MANIFEST.json",
                            json.dumps(manifest, ensure_ascii=False, indent=2))
                zf.writestr("README_RESTORE.txt",
                            "PubPartner working-data backup. Verify every manifest hash "
                            "before any recovery. This is not an Iteration Wallet sealed "
                            "snapshot. It omits cross-partner sessions and all managed "
                            "provider credential stores. Personal text may be sensitive.\n")
                for rel, path in sorted(selected.items()):
                    zf.write(path, arcname=f"pubpartner/{rel}")
            check = verify_friend_backup(temporary_target)
            if not check.get("ok"):
                raise RuntimeError("self-verification failed: " + str(check.get("error")))
            temporary_target.replace(target)
    finally:
        if temporary_target.exists():
            temporary_target.unlink()

    return {
        "ok": True, "format": BACKUP_FORMAT, "filename": filename,
        "path": str(target), "file_count": len(manifest["files"]),
        "size": target.stat().st_size, "sha256": _sha(target),
        "download_url": f"/api/pubpartner/backups/{filename}",
        "scope": "owner_and_partner",
        "backup_kind": "working_data_not_sealed_wallet_custody",
        "warnings": warnings,
        "contains_secrets": False,
    }


def verify_friend_backup(path: Path | str) -> Dict[str, Any]:
    """Read-only verification, rejecting extra entries, traversal, and tampering.

    A verified backup is still not automatically authorized for restoration.
    """
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return {"ok": False, "error": "backup not found"}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            manifest = json.loads(zf.read("PUBPARTNER_BACKUP_MANIFEST.json").decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != BACKUP_FORMAT:
                return {"ok": False, "error": "unsupported backup format"}
            # Older backups used fuzzy path matching and can contain foreign
            # records. Do not approve one for download/restore just because
            # its ZIP hashes match. Create a new strictly scoped backup.
            if manifest.get("scope") != "owner_and_partner":
                return {"ok": False, "error": "legacy unscoped backup; re-export required"}
            rows = manifest.get("files")
            if not isinstance(rows, list):
                return {"ok": False, "error": "invalid file manifest"}
            names = zf.namelist()
            if len(names) != len(set(names)):
                return {"ok": False, "error": "duplicate ZIP entries"}
            expected = {"PUBPARTNER_BACKUP_MANIFEST.json", "README_RESTORE.txt"}
            paths_seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    return {"ok": False, "error": "invalid manifest row"}
                rel = row.get("path")
                if not isinstance(rel, str) or not rel or "\\" in rel:
                    return {"ok": False, "error": "invalid manifest path"}
                parts = Path(rel).parts
                if (rel.startswith("/") or len(parts) < 2 or
                    any(part in ("", ".", "..") for part in parts)):
                    return {"ok": False, "error": "unsafe manifest path", "path": rel}
                if rel in paths_seen:
                    return {"ok": False, "error": "duplicate manifest path", "path": rel}
                paths_seen.add(rel)
                arc = "pubpartner/" + rel
                expected.add(arc)
                info = zf.getinfo(arc)
                if info.is_dir() or info.file_size != row.get("size"):
                    return {"ok": False, "error": "size mismatch", "path": rel}
                digest = hashlib.sha256()
                with zf.open(info, "r") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != row.get("sha256"):
                    return {"ok": False, "error": "hash mismatch", "path": rel}
            if set(names) != expected:
                return {"ok": False, "error": "unexpected or missing ZIP entries"}
            return {"ok": True, "files": len(rows), "manifest": manifest}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}



__all__ = ["create_friend_backup", "verify_friend_backup", "BACKUP_FORMAT"]
