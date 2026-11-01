"""Iteration Wallet v2.1 custody vault.

This is the active custody engine for the standalone Iteration Wallet build. It
implements the boring, load-bearing rules first: copy into custody, never delete,
never silently overwrite Prime/Cradle, record protected moves, and expose only a
closed catalog that is safe for AI or UI surfaces to inspect.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class VaultError(RuntimeError):
    """Base error for expected vault failures."""


class CeremonyRequiredError(VaultError):
    """Raised when a protected custody move lacks human ceremony proof."""


class FileState:
    RAW_SOURCE = "raw_source"
    CANDIDATE = "candidate"
    PRIME = "prime"
    ARCHIVE = "archive"
    REMOVED = "removed"
    QUARANTINE = "quarantine"
    RELEASED = "released"


PROTECTED_FIELDS = {
    "original_path",
    "vault_path",
    "sha256",
    "notes",
    "contents",
    "preview",
    "open_url",
    "run_url",
    "export_url",
    "ceremony_token",
    "raw_token",
    "token_secret",
}


@dataclass
class FileRecord:
    id: str
    name: str
    state: str
    original_path: str
    vault_path: str
    sha256: str
    size_bytes: int
    created_at: str
    last_modified: str
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileRecord":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            state=str(data["state"]),
            original_path=str(data.get("original_path", "")),
            vault_path=str(data.get("vault_path", "")),
            sha256=str(data.get("sha256") or data.get("hash") or ""),
            size_bytes=int(data.get("size_bytes", 0)),
            created_at=str(data.get("created_at", "")),
            last_modified=str(data.get("last_modified", "")),
            notes=str(data.get("notes", "")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class Section:
    id: str
    name: str
    description: str = ""
    created_at: str = ""
    raw_sources: List[FileRecord] = field(default_factory=list)
    candidates: List[FileRecord] = field(default_factory=list)
    prime: Optional[FileRecord] = None
    archive: List[FileRecord] = field(default_factory=list)
    removed: List[FileRecord] = field(default_factory=list)
    quarantine: List[FileRecord] = field(default_factory=list)
    released: List[FileRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Section":
        def records(key: str) -> List[FileRecord]:
            return [FileRecord.from_dict(item) for item in data.get(key, [])]

        prime = data.get("prime")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            created_at=str(data.get("created_at", "")),
            raw_sources=records("raw_sources"),
            candidates=records("candidates"),
            prime=FileRecord.from_dict(prime) if prime else None,
            archive=records("archive"),
            removed=records("removed"),
            quarantine=records("quarantine"),
            released=records("released"),
        )


@dataclass
class Project:
    id: str
    name: str
    root_path: str = ""
    created_at: str = ""
    sections: List[Section] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            root_path=str(data.get("root_path", "")),
            created_at=str(data.get("created_at", "")),
            sections=[Section.from_dict(item) for item in data.get("sections", [])],
        )


class VaultEngine:
    """Non-destructive custody engine for Cradle, Archive, and quarantine.

    The engine copies user material into custody. It does not execute custodied
    files, does not delete originals, and does not delete vault copies. Removing
    a file means moving its record to a protected holding state.
    """

    def __init__(
        self,
        vault_root: str | Path,
        *,
        blackbox: Optional[Any] = None,
        ceremony_ledger: Optional[Any] = None,
        strict_ceremony_tokens: bool = False,
    ) -> None:
        self.vault_root = Path(vault_root).expanduser().resolve()
        self.blackbox = blackbox
        self.ceremony_ledger = ceremony_ledger
        self.strict_ceremony_tokens = strict_ceremony_tokens
        self.projects_dir = self.vault_root / "projects"
        self.vault_files_dir = self.vault_root / "vault_files"
        self.rubish_dir = self.vault_root / "rubish"
        for directory in (self.projects_dir, self.vault_files_dir, self.rubish_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Project] = {}
        self._load_all_projects()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_all_projects(self) -> None:
        self._state.clear()
        for state_file in self.projects_dir.glob("*/state.json"):
            try:
                project = Project.from_dict(json.loads(state_file.read_text(encoding="utf-8")))
                self._state[project.id] = project
            except Exception as exc:
                self._record_event(
                    "VAULT_PROJECT_LOAD_FAILED",
                    "Project state could not be loaded",
                    state_file=str(state_file),
                    error=str(exc),
                )

    def _save_project(self, project: Project) -> None:
        self._write_json_atomic(self.projects_dir / project.id / "state.json", project.to_dict())

    def _record_event(self, event_type: str, summary: str, **extra: Any) -> Dict[str, Any]:
        if self.blackbox and hasattr(self.blackbox, "write_event"):
            return self.blackbox.write_event(event_type, summary, **extra)
        return {"event_type": event_type, "summary": summary, **extra}

    def _issue_receipt(self, *, action_key: str, action_label: str, project_id: str, section_id: str, file_id: str, object_name: str, custody_state: str, result_summary: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.blackbox and hasattr(self.blackbox, "issue_human_intent_receipt"):
            return self.blackbox.issue_human_intent_receipt(
                action_key=action_key,
                action_label=action_label,
                project_id=project_id,
                section_id=section_id,
                object_id=file_id,
                object_name=object_name,
                custody_state=custody_state,
                result_summary=result_summary,
                linked_event_hash=event.get("event_hash"),
            )
        return None

    def _require_project(self, project_id: str) -> Project:
        try:
            return self._state[project_id]
        except KeyError as exc:
            raise VaultError(f"Project not found: {project_id}") from exc

    def _require_section(self, project: Project, section_id: str) -> Section:
        for section in project.sections:
            if section.id == section_id:
                return section
        raise VaultError(f"Section not found: {section_id}")

    def _all_record_lists(self, section: Section) -> Iterable[List[FileRecord]]:
        yield section.raw_sources
        yield section.candidates
        yield section.archive
        yield section.removed
        yield section.quarantine
        yield section.released

    def _find_record_location(self, section: Section, file_id: str) -> tuple[FileRecord, Optional[List[FileRecord]], str]:
        if section.prime and section.prime.id == file_id:
            return section.prime, None, FileState.PRIME
        for records in self._all_record_lists(section):
            for record in records:
                if record.id == file_id:
                    return record, records, record.state
        raise VaultError(f"File record not found: {file_id}")

    def _consume_ceremony(self, token: Optional[str], scope: str) -> None:
        if not self.strict_ceremony_tokens and token:
            return
        if not token:
            raise CeremonyRequiredError(f"Human ceremony token required for {scope}")
        if not self.ceremony_ledger or not hasattr(self.ceremony_ledger, "consume"):
            raise CeremonyRequiredError("No ceremony ledger is available for protected action")
        if not self.ceremony_ledger.consume(token, scope=scope):
            raise CeremonyRequiredError("Ceremony token is invalid, expired, or already consumed")

    def _copy_into_vault(self, source_path: str | Path, file_id: str) -> tuple[Path, str, int]:
        source = Path(source_path).expanduser()
        if not source.exists() or not source.is_file():
            raise VaultError(f"Source file does not exist or is not a file: {source_path}")
        target_dir = self.vault_files_dir / file_id[:2]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{file_id}_{source.name}"
        if target.exists():
            raise VaultError(f"Vault target already exists; refusing overwrite: {target.name}")
        shutil.copy2(source, target)
        return target, self._sha256(target), target.stat().st_size

    def _new_record(self, source_path: str | Path, state: str, notes: str = "") -> FileRecord:
        file_id = uuid.uuid4().hex[:16]
        vault_path, digest, size = self._copy_into_vault(source_path, file_id)
        source = Path(source_path).expanduser()
        now = self._now()
        return FileRecord(
            id=file_id,
            name=source.name,
            state=state,
            original_path=str(source.resolve()),
            vault_path=str(vault_path),
            sha256=digest,
            size_bytes=size,
            created_at=now,
            last_modified=now,
            notes=notes,
        )

    def create_project(self, name: str, root_path: str = "") -> Dict[str, Any]:
        if not name.strip():
            raise VaultError("Project name is required")
        project = Project(
            id=uuid.uuid4().hex[:12],
            name=name.strip(),
            root_path=str(root_path or ""),
            created_at=self._now(),
        )
        self._state[project.id] = project
        self._save_project(project)
        self._record_event("PROJECT_CREATED", "Project created", project_id=project.id, project_name=project.name)
        return project.to_dict()

    def create_section(self, project_id: str, name: str, description: str = "") -> Dict[str, Any]:
        project = self._require_project(project_id)
        section = Section(
            id=uuid.uuid4().hex[:12],
            name=name.strip() or "Untitled Section",
            description=description,
            created_at=self._now(),
        )
        project.sections.append(section)
        self._save_project(project)
        self._record_event("SECTION_CREATED", "Section created", project_id=project_id, section_id=section.id)
        return section.to_dict()

    def add_raw_source(self, project_id: str, section_id: str, source_path: str, notes: str = "") -> Dict[str, Any]:
        project = self._require_project(project_id)
        section = self._require_section(project, section_id)
        record = self._new_record(source_path, FileState.RAW_SOURCE, notes)
        section.raw_sources.append(record)
        self._save_project(project)
        self._record_event("RAW_SOURCE_ADDED", "Raw source copied into custody", project_id=project_id, section_id=section_id, file_id=record.id, state=record.state)
        return record.to_dict()

    def add_candidate(self, project_id: str, section_id: str, source_path: str, notes: str = "") -> Dict[str, Any]:
        project = self._require_project(project_id)
        section = self._require_section(project, section_id)
        record = self._new_record(source_path, FileState.CANDIDATE, notes)
        section.candidates.append(record)
        self._save_project(project)
        self._record_event("CANDIDATE_ADDED", "Candidate copied into custody", project_id=project_id, section_id=section_id, file_id=record.id, state=record.state)
        return record.to_dict()

    def promote_to_prime(self, project_id: str, section_id: str, candidate_id: str, ceremony_token: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        self._consume_ceremony(ceremony_token, "promote_to_prime")
        project = self._require_project(project_id)
        section = self._require_section(project, section_id)
        candidate, records, _state = self._find_record_location(section, candidate_id)
        if records is not section.candidates:
            raise VaultError("Only candidate records can be promoted to Prime")
        if section.prime:
            section.prime.state = FileState.ARCHIVE
            section.prime.last_modified = self._now()
            section.archive.append(section.prime)
        records.remove(candidate)
        candidate.state = FileState.PRIME
        candidate.last_modified = self._now()
        candidate.metadata["prime_reason"] = reason
        section.prime = candidate
        self._save_project(project)
        event = self._record_event("PROMOTED_TO_PRIME", "Candidate promoted to Prime/Cradle", project_id=project_id, section_id=section_id, file_id=candidate.id, state=FileState.PRIME, reason=reason)
        receipt = self._issue_receipt(action_key="promote_candidate_to_prime", action_label="Promote Candidate to Prime", project_id=project_id, section_id=section_id, file_id=candidate.id, object_name=candidate.name, custody_state=FileState.PRIME, result_summary="Candidate promoted to Prime/Cradle", event=event)
        return {"result": candidate.to_dict(), "event": event, "receipt": receipt, "message": "Candidate promoted to Prime. The Cradle now holds this version."}

    def move_to_removed(self, project_id: str, section_id: str, file_id: str, ceremony_token: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        self._consume_ceremony(ceremony_token, "move_to_removed")
        project = self._require_project(project_id)
        section = self._require_section(project, section_id)
        record, records, state = self._find_record_location(section, file_id)
        if state == FileState.PRIME:
            section.prime = None
        elif records is not None:
            records.remove(record)
        record.state = FileState.REMOVED
        record.last_modified = self._now()
        record.metadata["removed_reason"] = reason
        section.removed.append(record)
        self._save_project(project)
        event = self._record_event("FILE_MOVED_TO_REMOVED", "File moved to removed holding; no bytes deleted", project_id=project_id, section_id=section_id, file_id=file_id, state=FileState.REMOVED, reason=reason)
        receipt = self._issue_receipt(action_key="remove_from_active", action_label="Remove from active use", project_id=project_id, section_id=section_id, file_id=file_id, object_name=record.name, custody_state=FileState.REMOVED, result_summary="File moved to removed holding; no bytes deleted", event=event)
        return {"result": record.to_dict(), "event": event, "receipt": receipt}

    def quarantine_file(self, project_id: str, section_id: str, file_id: str, reason: str = "") -> Dict[str, Any]:
        project = self._require_project(project_id)
        section = self._require_section(project, section_id)
        record, records, state = self._find_record_location(section, file_id)
        if state == FileState.PRIME:
            section.prime = None
        elif records is not None:
            records.remove(record)
        record.state = FileState.QUARANTINE
        record.last_modified = self._now()
        record.metadata["quarantine_reason"] = reason
        section.quarantine.append(record)
        self._save_project(project)
        event = self._record_event("FILE_QUARANTINED", "File record quarantined; no bytes deleted or executed", project_id=project_id, section_id=section_id, file_id=file_id, state=FileState.QUARANTINE, reason=reason)
        receipt = self._issue_receipt(action_key="quarantine", action_label="Quarantine file", project_id=project_id, section_id=section_id, file_id=file_id, object_name=record.name, custody_state=FileState.QUARANTINE, result_summary="File record quarantined; no bytes deleted or executed", event=event)
        return {"result": record.to_dict(), "event": event, "receipt": receipt}

    def restore_file(self, project_id: str, section_id: str, file_id: str, target_state: str = FileState.CANDIDATE) -> Dict[str, Any]:
        if target_state not in {FileState.CANDIDATE, FileState.ARCHIVE}:
            raise VaultError("Restore target must be candidate or archive")
        project = self._require_project(project_id)
        section = self._require_section(project, section_id)
        record, records, _state = self._find_record_location(section, file_id)
        if records is not section.removed and records is not section.quarantine and records is not section.archive:
            raise VaultError("Only removed, quarantined, or archived records can be restored this way")
        records.remove(record)
        record.state = target_state
        record.last_modified = self._now()
        if target_state == FileState.CANDIDATE:
            section.candidates.append(record)
        else:
            section.archive.append(record)
        self._save_project(project)
        event = self._record_event("FILE_RESTORED", "File restored from holding", project_id=project_id, section_id=section_id, file_id=file_id, state=target_state)
        return {"result": record.to_dict(), "event": event}

    def get_project(self, project_id: str) -> Dict[str, Any]:
        return self._require_project(project_id).to_dict()

    def list_projects(self) -> List[Dict[str, Any]]:
        return [project.to_dict() for project in sorted(self._state.values(), key=lambda item: item.created_at)]

    def get_section_view(self, project_id: str, section_id: str) -> Dict[str, Any]:
        project = self._require_project(project_id)
        return self._require_section(project, section_id).to_dict()

    @staticmethod
    def _scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: VaultEngine._scrub(child) for key, child in value.items() if key not in PROTECTED_FIELDS}
        if isinstance(value, list):
            return [VaultEngine._scrub(child) for child in value]
        return value

    def get_closed_catalog_view(self, project_id: str, section_id: str) -> Dict[str, Any]:
        view = self.get_section_view(project_id, section_id)
        closed = self._scrub(view)
        closed["closed_catalog_safe"] = True
        return closed

    def verify_custody_integrity(self) -> Dict[str, Any]:
        checked = 0
        failures: List[Dict[str, str]] = []
        for project in self._state.values():
            for section in project.sections:
                records: List[FileRecord] = []
                for bucket in self._all_record_lists(section):
                    records.extend(bucket)
                if section.prime:
                    records.append(section.prime)
                for record in records:
                    checked += 1
                    path = Path(record.vault_path)
                    if not path.exists():
                        failures.append({"file_id": record.id, "reason": "vault copy missing"})
                        continue
                    actual = self._sha256(path)
                    if actual != record.sha256:
                        failures.append({"file_id": record.id, "reason": "sha256 mismatch"})
        result = {"ok": not failures, "checked": checked, "failures": failures}
        self._record_event("CUSTODY_INTEGRITY_VERIFIED", "Custody integrity check completed", **result)
        return result


VaultEngineV21 = VaultEngine


__all__ = [
    "CeremonyRequiredError",
    "FileRecord",
    "FileState",
    "Project",
    "Section",
    "VaultEngine",
    "VaultEngineV21",
    "VaultError",
]


