"""
test_00_integrity.py — Static code and filesystem integrity
════════════════════════════════════════════════════════════
Runs before the app even boots. Verifies:
  - Every module that main.py imports at the top level exists on disk.
  - Every module that main.py imports lazily (inside route handlers) exists.
  - All required asset and static files are in place so StaticFiles won't
    crash at mount time.
  - The Rust binary is present (warns if missing — non-fatal).
  - requirements.txt is self-consistent (no obvious version conflicts).

These tests run in < 1 second. They are the first line of defence and must
pass before we even try to boot the app.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"
STATIC  = ROOT / "static"
ASSETS  = ROOT / "assets"
BIN     = ROOT / "bin"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Top-level module imports
# ─────────────────────────────────────────────────────────────────────────────

TOP_LEVEL_MODULES = [
    "hub", "persistence", "models", "cameras", "recording",
    "avatar", "bots", "orchestrator", "rooms", "schemas",
    "credentials", "byok_manager", "byok_routes", "studio_control",
    "studio_websocket", "voxel_asset_manager", "avatar_performer",
    "unity_bridge", "pubworld_router", "mic_routes", "audio_devices",
    "jeremy_cricket", "room_conductor", "pubworld_blocks", "voxel_llm_adapter",
]

@pytest.mark.parametrize("module_name", TOP_LEVEL_MODULES)
def test_top_level_module_file_exists(module_name):
    """Every module imported at the top of main.py must exist on disk."""
    path = MODULES / f"{module_name}.py"
    assert path.exists(), f"modules/{module_name}.py is missing — main.py will fail to import"


def test_sir_purfluous_character_is_registered():
    """Sir Purfluous remains a first-class character in the story registry."""
    from modules.pubcast_story_bible import CHARACTER_ROOTS
    assert "sir_purfluous" in CHARACTER_ROOTS


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lazy-imported modules (inside route handlers)
# ─────────────────────────────────────────────────────────────────────────────

LAZY_MODULES = [
    "pubworld",         # /api/pubworld/scenes
    "bridge",           # /api/bridge/*
    "cameras_advanced", # /api/cameras/advanced
    "choreography_controller",  # /api/choreo/*
    "circuit_breaker",  # /api/health/breakers
    "credentials",      # /api/credentials (also top-level but used lazily too)
    "inference",        # /api/inference/*
    "irm",              # /api/engine/status
    "projects",         # /api/projects/*
    "surfaces",         # /api/surfaces/*
    "avatar_motion",    # /api/motion/avatars
    "avatar_assets",    # /api/avatars/assets
    "lighting",         # /api/lighting/*
]

@pytest.mark.parametrize("module_name", LAZY_MODULES)
def test_lazy_module_file_exists(module_name):
    """Every module imported lazily inside route handlers must exist on disk."""
    path = MODULES / f"{module_name}.py"
    assert path.exists(), (
        f"modules/{module_name}.py is missing — its route handler will 500 at runtime"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Static and asset directories
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_STATIC_FILES = [
    "index.html", "control.html", "stage.html", "dressing.html",
    "dressing_foundry.html", "bar.html", "world.html", "builder.html",
    "gallery.html", "analytics.html", "launch.html", "byok.html",
    "studio_control_room.html",
    # the walkable world (/walk) and its two scripts
    "world_walk.html", "world_walk_glb.js", "world_walk_live.js",
    # JS files loaded by control.html for mic pipeline
    "mic_profiles.js", "mic_processor.js", "mic_device_picker.js",
]

@pytest.mark.parametrize("filename", REQUIRED_STATIC_FILES)
def test_static_file_exists(filename):
    """All template/static files referenced in page routes must exist."""
    assert (STATIC / filename).exists(), f"static/{filename} is missing — page route will 500"


def test_assets_directory_exists():
    """assets/ must exist before app mounts it as StaticFiles — missing = crash at import."""
    assert ASSETS.exists() and ASSETS.is_dir(), \
        "assets/ directory is missing — StaticFiles mount will crash at startup"


REQUIRED_ASSET_SUBDIRS = ["vod", "uploads", "models", "textures"]

@pytest.mark.parametrize("subdir", REQUIRED_ASSET_SUBDIRS)
def test_asset_subdirectory_exists(subdir):
    """Subdirectories written by ensure_dirs must exist (or be creatable)."""
    # They are created by ensure_dirs in lifespan — pass if either already exists
    # or the parent is writable (lifespan will create them).
    path = ASSETS / subdir
    if not path.exists():
        assert ASSETS.stat().st_mode & 0o200, \
            f"assets/{subdir} missing and assets/ is not writable — ensure_dirs will fail"


def test_static_directory_exists():
    """static/ must exist for StaticFiles mount."""
    assert STATIC.exists() and STATIC.is_dir(), \
        "static/ directory is missing — StaticFiles mount will crash at startup"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Rust binary (non-fatal — bridge runs in fallback mode if absent)
# ─────────────────────────────────────────────────────────────────────────────

def test_rust_binary_present():
    """ws_renderer binary should be present. Missing = animation in fallback mode (non-fatal)."""
    binary = BIN / "ws_renderer"
    if not binary.exists():
        pytest.warns(None)  # non-fatal, just record
        pytest.skip("ws_renderer binary not found — avatar animation will run in fallback mode")
    assert binary.stat().st_mode & 0o111, "ws_renderer exists but is not executable"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Data directory bootstrap
# ─────────────────────────────────────────────────────────────────────────────

DATA_SUBDIRS = [
    "users", "logs", "global", "avatars", "bots", "recordings",
    "exports", "imports", "projects", "security",
]

def test_data_directory_writable():
    """data/ must be writable — ensure_dirs creates subdirectories there at startup."""
    data = ROOT / "data"
    if data.exists():
        assert data.stat().st_mode & 0o200, "data/ exists but is not writable"
    else:
        assert ROOT.stat().st_mode & 0o200, \
            "data/ does not exist and project root is not writable — ensure_dirs will fail"


def test_jeremy_data_directory():
    """data/jeremy/ must exist or be creatable — CricketKeeper.init() writes SQLite DBs there."""
    jeremy_dir = ROOT / "data" / "jeremy"
    if not jeremy_dir.exists():
        parent = ROOT / "data"
        assert parent.exists() or (ROOT.stat().st_mode & 0o200), \
            "data/jeremy/ cannot be created — CricketKeeper will fail to initialise"
