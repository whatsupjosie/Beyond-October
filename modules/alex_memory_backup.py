"""Alex persistent-memory backup: local-folder and Google Drive backends.

Scope is exactly Alex's own files under ``<data_dir>/alex/<user_id>/``:
  * ``<YYYY-MM>/mem_*.json``   diary memories
  * ``_alex_state.json`` / ``_affect_state.json``   state snapshot, personal baseline/prior
Nothing else is read, so secrets/BYOK/provider keys can never be included.

Guarantees
  * Append-only: a local deletion never deletes the backup.
  * Change detection by SHA-256 against a manifest stored in the backup itself.
  * The manifest is written LAST, so an interrupted backup leaves a consistent older manifest.
  * Restore verifies every file's hash and never overwrites local files unless asked.
  * Backup errors are collected and reported; they never raise into a conversation turn.

Backends (use either or both via ``MirroredBackend``):
  * ``LocalFolderBackend`` - any folder; point it at a Google Drive for Desktop synced folder.
  * ``GoogleDriveBackend`` - Drive API v3 through an injected ``service`` object.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol

FORMAT = "AlexMemoryBackup.v1"
MANIFEST_NAME = "_backup_manifest.json"
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
DEFAULT_SCOPES = ("https://www.googleapis.com/auth/drive",)

_REL_OK = re.compile(r"^(?:_[A-Za-z0-9_]+\.json|\d{4}-\d{2}/mem_[A-Za-z0-9_.\-]+\.json)$")
_SAFE_USER = re.compile(r"[^A-Za-z0-9._-]")
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def safe_user(user_id: str) -> str:
    cleaned = _SAFE_USER.sub("_", str(user_id or "default"))[:128].strip(".")
    return cleaned or "default"


def valid_relpath(rel: str) -> bool:
    """Only Alex's own file shapes; rejects traversal, absolute and hidden paths."""
    return bool(isinstance(rel, str) and _REL_OK.match(rel) and ".." not in rel)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- backends

class BackupBackend(Protocol):
    name: str
    def put_bytes(self, path: str, data: bytes) -> None: ...
    def get_bytes(self, path: str) -> Optional[bytes]: ...


def _check_backend_path(path: str) -> None:
    parts = path.split("/")
    if not path or path.startswith("/") or any(p in ("", ".", "..") for p in parts) or "\\" in path:
        raise ValueError(f"unsafe backup path: {path!r}")


class LocalFolderBackend:
    """Plain folder backend (e.g. a Google Drive for Desktop synced folder)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.name = f"local:{self.root}"

    def put_bytes(self, path: str, data: bytes) -> None:
        _check_backend_path(path)
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".tmp{os.getpid()}")
        tmp.write_bytes(data)
        os.replace(tmp, target)

    def get_bytes(self, path: str) -> Optional[bytes]:
        _check_backend_path(path)
        target = self.root / path
        return target.read_bytes() if target.is_file() else None


def _q(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveBackend:
    """Google Drive v3 backend.  ``service`` is a googleapiclient Drive resource.

    ``root_folder_id`` must be a folder the credentials can write to (shared with a
    service account, or owned by the OAuth user).  With the narrow ``drive.file`` scope
    the app only sees folders/files it created itself, so the default scope is ``drive``.
    """

    def __init__(self, service: Any, root_folder_id: str, *,
                 media_factory: Optional[Callable[[bytes, str], Any]] = None) -> None:
        if not root_folder_id:
            raise ValueError("root_folder_id is required")
        self._svc = service
        self._root = root_folder_id
        self._media = media_factory or self._default_media
        self._folders: Dict[str, str] = {"": root_folder_id}
        self._files: Dict[str, str] = {}
        self._lock = threading.RLock()
        self.name = f"drive:{root_folder_id}"

    @staticmethod
    def _default_media(data: bytes, mimetype: str) -> Any:
        from googleapiclient.http import MediaInMemoryUpload  # lazy: optional dependency
        return MediaInMemoryUpload(data, mimetype=mimetype, resumable=False)

    def _find(self, name: str, parent: str, *, folder: bool) -> Optional[str]:
        kind = f"mimeType = '{DRIVE_FOLDER_MIME}'" if folder else f"mimeType != '{DRIVE_FOLDER_MIME}'"
        resp = self._svc.files().list(
            q=f"name = '{_q(name)}' and '{_q(parent)}' in parents and {kind} and trashed = false",
            spaces="drive", fields="files(id,name)", pageSize=10,
            supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = resp.get("files") or []
        return files[0]["id"] if files else None

    def _ensure_folder(self, dir_path: str) -> str:
        if dir_path in self._folders:
            return self._folders[dir_path]
        parent_path, _, leaf = dir_path.rpartition("/")
        parent = self._ensure_folder(parent_path)
        found = self._find(leaf, parent, folder=True)
        if found is None:
            found = self._svc.files().create(
                body={"name": leaf, "mimeType": DRIVE_FOLDER_MIME, "parents": [parent]},
                fields="id", supportsAllDrives=True).execute()["id"]
        self._folders[dir_path] = found
        return found

    def _locate(self, path: str, *, create_dirs: bool) -> tuple[Optional[str], str]:
        dir_path, _, leaf = path.rpartition("/")
        if create_dirs:
            parent = self._ensure_folder(dir_path)
        else:
            parent = self._folders.get(dir_path)
            if parent is None:
                parent = self._root
                for part in [p for p in dir_path.split("/") if p]:
                    parent = self._find(part, parent, folder=True)
                    if parent is None:
                        return None, leaf
                self._folders[dir_path] = parent
        return parent, leaf

    def put_bytes(self, path: str, data: bytes) -> None:
        _check_backend_path(path)
        with self._lock:
            parent, leaf = self._locate(path, create_dirs=True)
            file_id = self._files.get(path) or self._find(leaf, parent, folder=False)
            media = self._media(data, "application/json")
            if file_id:
                self._svc.files().update(fileId=file_id, media_body=media, fields="id",
                                         supportsAllDrives=True).execute()
            else:
                file_id = self._svc.files().create(
                    body={"name": leaf, "parents": [parent]}, media_body=media,
                    fields="id", supportsAllDrives=True).execute()["id"]
            self._files[path] = file_id

    def get_bytes(self, path: str) -> Optional[bytes]:
        _check_backend_path(path)
        with self._lock:
            parent, leaf = self._locate(path, create_dirs=False)
            if parent is None:
                return None
            file_id = self._files.get(path) or self._find(leaf, parent, folder=False)
            if not file_id:
                return None
            self._files[path] = file_id
            data = self._svc.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
            return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")


class MirroredBackend:
    """Write to every backend, read from the first that has the file.

    A failing mirror never blocks the others; put errors are raised only if ALL fail.
    """

    def __init__(self, backends: Iterable[BackupBackend]) -> None:
        self.backends = [b for b in backends if b is not None]
        if not self.backends:
            raise ValueError("MirroredBackend needs at least one backend")
        self.name = "mirror[" + ", ".join(b.name for b in self.backends) + "]"
        self.last_errors: Dict[str, str] = {}

    def put_bytes(self, path: str, data: bytes) -> None:
        errors: Dict[str, str] = {}
        ok = 0
        for b in self.backends:
            try:
                b.put_bytes(path, data)
                ok += 1
            except Exception as exc:  # noqa: BLE001 - isolate per-backend failure
                errors[b.name] = f"{type(exc).__name__}: {exc}"
        self.last_errors = errors
        if ok == 0:
            raise RuntimeError("all backup backends failed: " + "; ".join(errors.values()))

    def get_bytes(self, path: str) -> Optional[bytes]:
        for b in self.backends:
            try:
                data = b.get_bytes(path)
            except Exception:  # noqa: BLE001
                continue
            if data is not None:
                return data
        return None


# --------------------------------------------------------------------------- engine

class AlexMemoryBackup:
    def __init__(self, data_dir: Path | str, backend: BackupBackend, *,
                 min_interval: float = 60.0, clock: Callable[[], float] = time.time) -> None:
        self.data_dir = Path(data_dir)
        self.backend = backend
        self.min_interval = max(0.0, float(min_interval))
        self._clock = clock
        self._last_run: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._threads: List[threading.Thread] = []
        self.last_report: Dict[str, Any] = {}

    # -- local layout -------------------------------------------------------
    @property
    def alex_root(self) -> Path:
        return self.data_dir / "alex"

    def local_users(self) -> List[str]:
        if not self.alex_root.is_dir():
            return []
        return sorted(p.name for p in self.alex_root.iterdir()
                      if p.is_dir() and not p.name.startswith("_") and p.name not in {"affect"})

    def _local_files(self, user_id: str) -> Dict[str, Path]:
        base = self.alex_root / user_id
        found: Dict[str, Path] = {}
        if not base.is_dir():
            return found
        for path in base.rglob("*.json"):
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(base).as_posix()
            if valid_relpath(rel):
                found[rel] = path
        return found

    @staticmethod
    def _remote(user_id: str, rel: str) -> str:
        return f"{safe_user(user_id)}/{rel}"

    def _manifest(self, user_id: str) -> Dict[str, Any]:
        raw = self.backend.get_bytes(self._remote(user_id, MANIFEST_NAME))
        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
                if data.get("format") == FORMAT and isinstance(data.get("files"), dict):
                    return data
            except (ValueError, UnicodeDecodeError):
                pass
        return {"format": FORMAT, "user_id": user_id, "contains_secrets": False, "files": {}}

    # -- backup --------------------------------------------------------------
    def backup(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        users = [user_id] if user_id else self.local_users()
        report: Dict[str, Any] = {"format": FORMAT, "backend": self.backend.name, "users": {},
                                  "uploaded": 0, "unchanged": 0, "errors": []}
        with self._lock:
            for uid in users:
                try:
                    r = self._backup_user(uid)
                except Exception as exc:  # noqa: BLE001
                    r = {"uploaded": 0, "unchanged": 0, "errors": [f"{type(exc).__name__}: {exc}"]}
                report["users"][uid] = r
                report["uploaded"] += r["uploaded"]
                report["unchanged"] += r["unchanged"]
                report["errors"] += [f"{uid}: {e}" for e in r["errors"]]
                self._last_run[uid] = self._clock()
            self.last_report = report
        return report

    def _backup_user(self, user_id: str) -> Dict[str, Any]:
        manifest = self._manifest(user_id)
        known = manifest["files"]
        uploaded = unchanged = 0
        errors: List[str] = []
        for rel, path in sorted(self._local_files(user_id).items()):
            try:
                data = path.read_bytes()
                digest = _sha(data)
                if known.get(rel, {}).get("sha256") == digest:
                    unchanged += 1
                    continue
                self.backend.put_bytes(self._remote(user_id, rel), data)
                known[rel] = {"sha256": digest, "size": len(data)}
                uploaded += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: {type(exc).__name__}: {exc}")
        if uploaded:
            manifest["updated_at"] = self._clock()
            manifest["count"] = len(known)
            self.backend.put_bytes(self._remote(user_id, MANIFEST_NAME),
                                   json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
        return {"uploaded": uploaded, "unchanged": unchanged, "errors": errors}

    def notify_turn(self, user_id: str, *, background: bool = True) -> bool:
        """Throttled, non-blocking backup after a turn.  Returns True if a run was started."""
        now = self._clock()
        with self._lock:
            if now - self._last_run.get(user_id, -1e18) < self.min_interval:
                return False
            self._last_run[user_id] = now
        if not background:
            self.backup(user_id)
            return True
        t = threading.Thread(target=self.backup, args=(user_id,), name="alex-memory-backup", daemon=True)
        self._threads = [x for x in self._threads if x.is_alive()] + [t]
        t.start()
        return True

    def wait(self, timeout: float = 30.0) -> None:
        for t in list(self._threads):
            t.join(timeout)

    # -- read access ("Alex can read anything in there") ----------------------
    def list_memories(self, user_id: str) -> List[str]:
        return sorted(r for r in self._manifest(user_id)["files"] if r.startswith(("1", "2")))

    def read(self, user_id: str, rel: str) -> Optional[Dict[str, Any]]:
        if not valid_relpath(rel) or rel == MANIFEST_NAME:
            raise ValueError(f"not an Alex memory path: {rel!r}")
        raw = self.backend.get_bytes(self._remote(user_id, rel))
        if raw is None:
            return None
        expected = self._manifest(user_id)["files"].get(rel, {}).get("sha256")
        if expected and expected != _sha(raw):
            raise ValueError(f"backup integrity check failed for {rel}")
        return json.loads(raw.decode("utf-8"))

    def search(self, user_id: str, query: str, *, limit: int = 5, max_chars: int = 280) -> List[Dict[str, Any]]:
        wanted = set(_TOKEN_RE.findall((query or "").lower()))
        if not wanted:
            return []
        hits = []
        for rel in self.list_memories(user_id):
            try:
                mem = self.read(user_id, rel)
            except Exception:  # noqa: BLE001
                continue
            if not mem:
                continue
            words = set(_TOKEN_RE.findall(str(mem.get("content", "")).lower()))
            words |= {w for k in mem.get("keywords", []) for w in _TOKEN_RE.findall(str(k).lower())}
            score = len(wanted & words)
            if score:
                text = " ".join(str(mem.get("content", "")).split())
                hits.append((score, str(mem.get("timestamp", "")), {
                    "id": mem.get("id", rel), "path": rel,
                    "text": text if len(text) <= max_chars else text[: max_chars - 1] + "…",
                    "at": mem.get("timestamp", "")}))
        hits.sort(key=lambda h: (h[0], h[1]), reverse=True)
        return [h[2] for h in hits[: max(1, int(limit))]]

    # -- restore -------------------------------------------------------------
    def restore(self, user_id: str, *, overwrite: bool = False) -> Dict[str, Any]:
        manifest = self._manifest(user_id)
        base = self.alex_root / user_id
        restored: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []
        for rel, meta in sorted(manifest["files"].items()):
            if not valid_relpath(rel):
                errors.append(f"{rel}: invalid path in manifest")
                continue
            target = base / rel
            if target.exists() and not overwrite:
                skipped.append(rel)
                continue
            raw = self.backend.get_bytes(self._remote(user_id, rel))
            if raw is None:
                errors.append(f"{rel}: missing from backup")
            elif meta.get("sha256") != _sha(raw):
                errors.append(f"{rel}: hash mismatch, not restored")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(target.name + f".tmp{os.getpid()}")
                tmp.write_bytes(raw)
                os.replace(tmp, target)
                restored.append(rel)
        return {"restored": restored, "skipped": skipped, "errors": errors}

    def restore_if_empty(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Disaster recovery: only when Alex has no local files at all."""
        if self._local_files(user_id):
            return None
        try:
            return self.restore(user_id)
        except Exception as exc:  # noqa: BLE001
            return {"restored": [], "skipped": [], "errors": [f"{type(exc).__name__}: {exc}"]}

    def status(self) -> Dict[str, Any]:
        return {"format": FORMAT, "backend": self.backend.name, "min_interval": self.min_interval,
                "local_users": self.local_users(), "last_report": self.last_report}


# --------------------------------------------------------------------------- Google auth / env

def build_drive_service(credentials_file: str, token_file: Optional[str] = None,
                        scopes: Iterable[str] = DEFAULT_SCOPES, *, interactive: bool = False) -> Any:
    """Build a Drive v3 service from a service-account JSON or OAuth client JSON.

    Needs: pip install google-api-python-client google-auth google-auth-oauthlib
    """
    from googleapiclient.discovery import build  # lazy: optional dependency
    scopes = list(scopes)
    info = json.loads(Path(credentials_file).read_text(encoding="utf-8"))
    if info.get("type") == "service_account":
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=scopes)
    else:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        creds = None
        if token_file and Path(token_file).is_file():
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            Path(token_file).write_text(creds.to_json(), encoding="utf-8")
        if not creds or not creds.valid:
            if not interactive:
                raise RuntimeError("no valid Google token; run: python -m modules.alex_memory_backup authorize")
            from google_auth_oauthlib.flow import InstalledAppFlow
            creds = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes).run_local_server(port=0)
            if token_file:
                Path(token_file).write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def build_alex_backup_from_env(data_dir: Path | str, env: Optional[Mapping[str, str]] = None) -> Optional[AlexMemoryBackup]:
    """Configure from environment.  Returns None when nothing is configured.

    ALEX_BACKUP_LOCAL_DIR            folder (e.g. Google Drive for Desktop sync folder)
    ALEX_BACKUP_DRIVE_FOLDER_ID      Drive folder id for the API backend
    ALEX_BACKUP_GOOGLE_CREDENTIALS   service-account or OAuth client JSON
    ALEX_BACKUP_GOOGLE_TOKEN         cached OAuth token (OAuth only)
    ALEX_BACKUP_MIN_INTERVAL         seconds between automatic backups (default 60)
    """
    env = os.environ if env is None else env
    backends: List[BackupBackend] = []
    if env.get("ALEX_BACKUP_LOCAL_DIR"):
        backends.append(LocalFolderBackend(env["ALEX_BACKUP_LOCAL_DIR"]))
    if env.get("ALEX_BACKUP_DRIVE_FOLDER_ID") and env.get("ALEX_BACKUP_GOOGLE_CREDENTIALS"):
        try:
            service = build_drive_service(env["ALEX_BACKUP_GOOGLE_CREDENTIALS"], env.get("ALEX_BACKUP_GOOGLE_TOKEN"))
            backends.append(GoogleDriveBackend(service, env["ALEX_BACKUP_DRIVE_FOLDER_ID"]))
        except Exception as exc:  # noqa: BLE001 - the local backend must still work
            print(f"[alex-backup] Google Drive backend unavailable: {type(exc).__name__}: {exc}")
    if not backends:
        return None
    backend: BackupBackend = backends[0] if len(backends) == 1 else MirroredBackend(backends)
    return AlexMemoryBackup(data_dir, backend, min_interval=float(env.get("ALEX_BACKUP_MIN_INTERVAL", "60") or 60))


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="python -m modules.alex_memory_backup")
    p.add_argument("command", choices=["authorize", "backup", "status", "restore", "search"])
    p.add_argument("--data-dir", default=os.getenv("PUBCAST_DATA_DIR", "data"))
    p.add_argument("--user", default=None)
    p.add_argument("--query", default="")
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    if a.command == "authorize":
        cred, tok = os.getenv("ALEX_BACKUP_GOOGLE_CREDENTIALS"), os.getenv("ALEX_BACKUP_GOOGLE_TOKEN")
        if not cred or not tok:
            print("set ALEX_BACKUP_GOOGLE_CREDENTIALS (OAuth client JSON) and ALEX_BACKUP_GOOGLE_TOKEN (where to save the token)")
            return 2
        build_drive_service(cred, tok, interactive=True)
        print("authorized; token saved to", tok)
        return 0
    engine = build_alex_backup_from_env(a.data_dir)
    if engine is None:
        print("no backup configured (see ALEX_BACKUP_* variables)")
        return 2
    if a.command == "status":
        print(json.dumps(engine.status(), indent=2, default=str))
    elif a.command == "backup":
        print(json.dumps(engine.backup(a.user), indent=2, default=str))
    elif a.command == "restore":
        if not a.user:
            print("--user is required")
            return 2
        print(json.dumps(engine.restore(a.user, overwrite=a.overwrite), indent=2))
    else:
        if not a.user:
            print("--user is required")
            return 2
        print(json.dumps(engine.search(a.user, a.query), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
