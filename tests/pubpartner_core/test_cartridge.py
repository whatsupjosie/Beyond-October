import zipfile
from pathlib import Path

import pytest

from pubpartner.cartridge import CartridgeValidationError, init_cartridge, load_cartridge


def test_init_and_load_roundtrip(tmp_path: Path):
    cart_dir = tmp_path / "alex"
    init_cartridge(
        cart_dir,
        name="Alex",
        summary="A steady, curious presence.",
        cadence="short declarative sentences, occasional trailing thought",
        vocabulary="plain, warm, avoids jargon",
    )
    cartridge = load_cartridge(cart_dir)
    try:
        assert cartridge.name == "Alex"
        assert cartridge.definition.voice.cadence.startswith("short declarative")
        assert cartridge.memory.count() == 0
    finally:
        cartridge.close()


def test_init_refuses_nonempty_directory(tmp_path: Path):
    cart_dir = tmp_path / "alex"
    cart_dir.mkdir()
    (cart_dir / "existing.txt").write_text("hi")
    with pytest.raises(FileExistsError):
        init_cartridge(cart_dir, name="Alex", summary="x", cadence="x", vocabulary="x")


def test_load_missing_path_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_cartridge(tmp_path / "does_not_exist")


def test_load_missing_required_file(tmp_path: Path):
    cart_dir = tmp_path / "broken"
    cart_dir.mkdir()
    (cart_dir / "character.yaml").write_text("name: X\nsummary: y\n")
    with pytest.raises(CartridgeValidationError, match="voice_profile.yaml"):
        load_cartridge(cart_dir)


def test_load_malformed_yaml(tmp_path: Path):
    cart_dir = tmp_path / "broken"
    cart_dir.mkdir()
    (cart_dir / "character.yaml").write_text("name: [unclosed")
    (cart_dir / "voice_profile.yaml").write_text("cadence: x\nvocabulary: y\n")
    with pytest.raises(CartridgeValidationError, match="not valid YAML"):
        load_cartridge(cart_dir)


def test_load_missing_required_field(tmp_path: Path):
    cart_dir = tmp_path / "broken"
    cart_dir.mkdir()
    (cart_dir / "character.yaml").write_text("name: X\n")  # missing summary
    (cart_dir / "voice_profile.yaml").write_text("cadence: x\nvocabulary: y\n")
    with pytest.raises(CartridgeValidationError, match="summary"):
        load_cartridge(cart_dir)


def test_load_from_zip(tmp_path: Path):
    cart_dir = tmp_path / "alex"
    init_cartridge(cart_dir, name="Alex", summary="s", cadence="c", vocabulary="v")

    zip_path = tmp_path / "alex.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in cart_dir.iterdir():
            zf.write(f, arcname=f"alex/{f.name}")

    cartridge = load_cartridge(zip_path)
    try:
        assert cartridge.name == "Alex"
    finally:
        cartridge.close()


def test_seed_memories_loaded_on_first_open(tmp_path: Path):
    cart_dir = tmp_path / "alex"
    init_cartridge(cart_dir, name="Alex", summary="s", cadence="c", vocabulary="v")
    (cart_dir / "memories.jsonl").write_text(
        '{"text": "Loves tide pools.", "memory_type": "personal", "importance": 0.6}\n'
    )
    cartridge = load_cartridge(cart_dir)
    try:
        assert cartridge.memory.count() == 1
    finally:
        cartridge.close()

    # second open should not duplicate seed memories
    cartridge2 = load_cartridge(cart_dir)
    try:
        assert cartridge2.memory.count() == 1
    finally:
        cartridge2.close()
