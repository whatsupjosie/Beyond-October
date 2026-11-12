"""Regression: both camera managers must actually persist their configuration.

The production save methods previously swallowed NameError for write_json.
This test checks disk state rather than just that save_configuration returns.
"""
import importlib
import json

import pytest


@pytest.mark.parametrize(
    "module_name",
    ["modules.cameras_advanced", "modules.evo.camera_manager"],
)
def test_camera_configuration_saves_and_updates_on_disk(tmp_path, module_name):
    manager_cls = importlib.import_module(module_name).AdvancedCameraManager
    manager = manager_cls.__new__(manager_cls)
    manager.config_path = tmp_path / "camera_config.json"
    manager.sources = {}
    manager.program_source = "camera-a"
    manager.preview_source = None
    manager.recording_sources = ["camera-a"]
    manager.auto_switch_rules = []

    manager.save_configuration()

    assert manager.config_path.is_file(), (
        "save_configuration returned but no configuration was written"
    )
    saved = json.loads(manager.config_path.read_text(encoding="utf-8"))
    assert saved["cameras"] == []
    assert saved["production_state"]["program_source"] == "camera-a"
    assert saved["production_state"]["recording_sources"] == ["camera-a"]

    manager.program_source = "camera-b"
    manager.recording_sources = ["camera-b"]
    manager.save_configuration()

    saved_again = json.loads(manager.config_path.read_text(encoding="utf-8"))
    assert saved_again["production_state"]["program_source"] == "camera-b"
    assert saved_again["production_state"]["recording_sources"] == ["camera-b"]
