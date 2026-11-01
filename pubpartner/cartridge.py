"""
Cartridge loading and validation.

A cartridge on disk is a directory (or a zip of one) with this layout:

    my_character/
        character.yaml         # required — identity, values, tendencies
        voice_profile.yaml     # required — cadence, vocabulary, tics
        appearance.yaml        # optional — physical/visual description
        memories.jsonl         # optional — seed memories, one JSON object per line
        memories.db            # auto-created — persistent memory store

Loading a cartridge validates every required file and field up front, so a
malformed cartridge fails loudly at load time instead of producing silently
wrong prompts later.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from .memory_store import MemoryStore
from .schema import (
    Appearance,
    CartridgeValidationError,
    CharacterDefinition,
    Identity,
    VoiceProfile,
)

REQUIRED_FILES = ("character.yaml", "voice_profile.yaml")


@dataclass
class Cartridge:
    """A loaded, validated cartridge ready for use."""

    path: Path
    definition: CharacterDefinition
    memory: MemoryStore

    @property
    def name(self) -> str:
        return self.definition.name

    def close(self) -> None:
        self.memory.close()

    def __enter__(self) -> "Cartridge":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _load_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise CartridgeValidationError(f"{path.name} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CartridgeValidationError(f"{path.name} must contain a YAML mapping at the top level")
    return data


def load_cartridge(source: str | Path) -> Cartridge:
    """Load a cartridge from a directory or a .zip archive of one.

    Raises CartridgeValidationError with a specific, actionable message if
    any required file or field is missing or malformed. Raises
    FileNotFoundError if the source path doesn't exist at all.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Cartridge path does not exist: {source}")

    cleanup_dir: Path | None = None
    if source.is_file():
        if source.suffix != ".zip":
            raise CartridgeValidationError(
                f"Cartridge file must be a .zip archive, got: {source.suffix or '(no extension)'}"
            )
        cleanup_dir = Path(tempfile.mkdtemp(prefix="pubpartner_cartridge_"))
        with zipfile.ZipFile(source) as zf:
            zf.extractall(cleanup_dir)
        # A zip may contain a single top-level folder — descend into it if so.
        entries = list(cleanup_dir.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            cartridge_dir = entries[0]
        else:
            cartridge_dir = cleanup_dir
    elif source.is_dir():
        cartridge_dir = source
    else:
        raise CartridgeValidationError(f"Cartridge source is neither a file nor a directory: {source}")

    missing = [f for f in REQUIRED_FILES if not (cartridge_dir / f).exists()]
    if missing:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)
        raise CartridgeValidationError(
            f"Cartridge at {source} is missing required file(s): {', '.join(missing)}"
        )

    character_data = _load_yaml(cartridge_dir / "character.yaml")
    voice_data = _load_yaml(cartridge_dir / "voice_profile.yaml")
    appearance_path = cartridge_dir / "appearance.yaml"
    appearance_data = _load_yaml(appearance_path) if appearance_path.exists() else {}

    try:
        identity = Identity.from_dict(character_data)
        voice = VoiceProfile.from_dict(voice_data)
        appearance = Appearance.from_dict(appearance_data)
    except CartridgeValidationError:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)
        raise

    definition = CharacterDefinition(identity=identity, voice=voice, appearance=appearance)

    db_path = cartridge_dir / "memories.db"
    store = MemoryStore(db_path)

    seed_path = cartridge_dir / "memories.jsonl"
    if seed_path.exists() and store.count() == 0:
        store.seed_from_jsonl(seed_path)

    return Cartridge(path=cartridge_dir, definition=definition, memory=store)


def init_cartridge(
    directory: str | Path,
    name: str,
    summary: str,
    cadence: str,
    vocabulary: str,
) -> Path:
    """Scaffold a new, minimally valid cartridge on disk. Returns the path
    created. Fails if the directory already exists and is non-empty."""
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"Directory already exists and is not empty: {directory}")
    directory.mkdir(parents=True, exist_ok=True)

    character = {
        "name": name,
        "summary": summary,
        "values": [],
        "boundaries": [],
        "tendencies": [],
    }
    voice = {
        "cadence": cadence,
        "vocabulary": vocabulary,
        "verbal_tics": [],
        "sentence_length": "varied",
        "formality": "neutral",
    }
    appearance = {"description": "", "details": []}

    (directory / "character.yaml").write_text(yaml.safe_dump(character, sort_keys=False), encoding="utf-8")
    (directory / "voice_profile.yaml").write_text(yaml.safe_dump(voice, sort_keys=False), encoding="utf-8")
    (directory / "appearance.yaml").write_text(yaml.safe_dump(appearance, sort_keys=False), encoding="utf-8")
    (directory / "memories.jsonl").write_text("", encoding="utf-8")

    return directory
