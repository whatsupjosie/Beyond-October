"""Packaged identity metadata must not be parsed as executable bot config."""

import json
import logging
from pathlib import Path

from modules.bots import BotManager


def test_identity_metadata_is_preserved_and_not_reported_as_a_broken_bot(
    tmp_path, caplog
):
    directory = tmp_path / "bots"
    directory.mkdir()
    source = (
        Path(__file__).resolve().parents[1] / "data/bots/pete_character_identity.json"
    )
    identity = directory / source.name
    identity.write_bytes(source.read_bytes())
    valid = Path(__file__).resolve().parents[1] / "data/bots/pete.json"
    (directory / "pete.json").write_bytes(valid.read_bytes())
    with caplog.at_level(logging.ERROR):
        manager = BotManager(tmp_path, None)
    assert [c.bot_id for c in manager.list_configs()] == ["pete"]
    assert identity.read_bytes() == source.read_bytes()
    assert not any("Invalid bot config" in r.message for r in caplog.records)


def test_invalid_bot_json_is_reported_without_aborting_other_configs(tmp_path, caplog):
    directory = tmp_path / "bots"
    directory.mkdir()
    (directory / "not-an-object.json").write_text(json.dumps(["invalid"]))
    valid = Path(__file__).resolve().parents[1] / "data/bots/pete.json"
    (directory / "pete.json").write_bytes(valid.read_bytes())
    with caplog.at_level(logging.ERROR):
        manager = BotManager(tmp_path, None)
    assert [c.bot_id for c in manager.list_configs()] == ["pete"]
    assert any("Invalid bot config" in r.message for r in caplog.records)
