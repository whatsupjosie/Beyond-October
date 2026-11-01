import json
from pathlib import Path


def test_menu_coverage_has_help_and_safe_console():
    data = json.loads(Path("config/menu_coverage.json").read_text(encoding="utf-8"))
    ids = {menu["id"] for menu in data["menus"]}
    assert "help_recovery" in ids
    assert "safe_console" in ids


def test_fragile_systems_have_recovery_actions():
    data = json.loads(Path("config/menu_coverage.json").read_text(encoding="utf-8"))
    required = {"audio", "performance", "character", "recording_show", "scene_room"}
    by_id = {menu["id"]: menu for menu in data["menus"]}
    for menu_id in required:
        assert by_id[menu_id]["recovery"], menu_id


def test_safe_console_static_file_is_minimal():
    html = Path("static/safe_console.html").read_text(encoding="utf-8").lower()
    assert "pubcast safe console" in html
    assert "<img" not in html
    assert "autoplay" not in html
    assert "ask pub manager" in html


def test_menu_coverage_has_ai_conversation_without_blackbox_player_menu():
    data = json.loads(Path("config/menu_coverage.json").read_text(encoding="utf-8"))
    by_id = {menu["id"]: menu for menu in data["menus"]}
    assert "ai_conversation" in by_id
    assert "model_slots" in by_id["ai_conversation"]["systems"]
    assert "blackbox_witness" not in by_id
    for menu in data["menus"]:
        assert "blackbox" not in menu["systems"]
        assert "blackbox_status" not in menu["systems"]


def test_menu_coverage_exposes_switchblade_and_spine_without_blackbox():
    data = json.loads(Path("config/menu_coverage.json").read_text(encoding="utf-8"))
    by_id = {menu["id"]: menu for menu in data["menus"]}
    assert "switchblade_router" in by_id["ai_conversation"]["systems"]
    assert "background_math" in by_id["pub_partner_chat"]["systems"]
    assert "runtime_spine" in by_id["help_recovery"]["systems"]
    assert "runtime_spine_status" in by_id["safe_console"]["systems"]
    for menu in data["menus"]:
        assert "blackbox" not in menu["systems"]

def test_menu_coverage_places_voxel_block_kit_without_console_ui():
    data = json.loads(Path("config/menu_coverage.json").read_text(encoding="utf-8"))
    by_id = {menu["id"]: menu for menu in data["menus"]}
    assert "voxel_block_kit" in by_id["scene_room"]["systems"]
    assert "voxel_block_preview" in by_id["scene_room"]["systems"]
    assert "voxel_block_kit" in by_id["help_recovery"]["systems"]
    assert "voxel_block_preview" in by_id["help_recovery"]["systems"]
    assert "voxel_block_kit_status" in by_id["help_recovery"]["recovery"]
    assert "voxel_block_kit" not in by_id["safe_console"]["systems"]
    assert "voxel_block_preview" not in by_id["safe_console"]["systems"]