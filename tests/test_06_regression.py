"""
test_06_regression.py — Regression tests for known bugs
═════════════════════════════════════════════════════════
Each test here documents a specific bug that was found and fixed.
If someone re-introduces the bug, the test catches it before it ships.

Bug registry:
  REG-001  /ws/unity and /ws/studio shadowed by /ws/{room} catch-all
  REG-002  lighting_apply calls hub.broadcast_system_event without null guard
  REG-003  internal nudges re-enter generic chat and trigger bot feedback loops
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "main.py"


# ─────────────────────────────────────────────────────────────────────────────
# REG-001: WebSocket route shadowing
# ─────────────────────────────────────────────────────────────────────────────

def test_reg001_ws_unity_not_shadowed_by_ws_room(raw_app):
    """REG-001: /ws/unity must be registered before /ws/{room} in the route list.

    SYMPTOM: Unity Bridge WebSocket appeared to connect but silently failed —
    Hub returned {"type":"error"} for all Unity protocol messages.
    ROOT CAUSE: /ws/{room} registered before /ws/unity. Starlette first-match wins.
    FIX: Moved /ws/unity and /ws/studio before /ws/{room} in main.py.
    """
    from starlette.routing import WebSocketRoute
    ws_routes = [r for r in raw_app.routes if isinstance(r, WebSocketRoute)]
    paths = [r.path for r in ws_routes]

    assert "/ws/unity" in paths,   "REG-001: /ws/unity not registered"
    assert "/ws/{room}" in paths,  "REG-001: /ws/{room} not registered"

    unity_pos    = paths.index("/ws/unity")
    catchall_pos = paths.index("/ws/{room}")
    assert unity_pos < catchall_pos, (
        f"REG-001 REGRESSION: /ws/unity (pos {unity_pos}) comes after "
        f"/ws/{{room}} (pos {catchall_pos}). Unity Bridge is broken."
    )


def test_reg001_ws_studio_not_shadowed_by_ws_room(raw_app):
    """REG-001: /ws/studio must be registered before /ws/{room}."""
    from starlette.routing import WebSocketRoute
    ws_routes = [r for r in raw_app.routes if isinstance(r, WebSocketRoute)]
    paths = [r.path for r in ws_routes]

    assert "/ws/studio" in paths,  "REG-001: /ws/studio not registered"
    studio_pos   = paths.index("/ws/studio")
    catchall_pos = paths.index("/ws/{room}")
    assert studio_pos < catchall_pos, (
        f"REG-001 REGRESSION: /ws/studio (pos {studio_pos}) comes after "
        f"/ws/{{room}} (pos {catchall_pos}). Studio Control Room WS is broken."
    )


# ─────────────────────────────────────────────────────────────────────────────
# REG-002: Missing null guard on hub in lighting_apply (static AST check)
# ─────────────────────────────────────────────────────────────────────────────

def test_reg002_lighting_apply_has_hub_null_guard():
    """REG-002: lighting_apply must check `if hub is not None` before calling
    hub.broadcast_system_event().

    SYMPTOM: Calling /api/lighting/apply/{preset_id} during tests or before
    lifespan completes raised AttributeError: 'NoneType' has no attribute
    'broadcast_system_event'.
    FIX: Added `if hub is not None:` guard around the broadcast call.
    """
    source = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find the current lighting endpoint implementation. Older handoffs called
    # it ``lighting_apply``; Reach names it ``apply_lighting_preset``.
    lighting_fn = None
    accepted_names = {"apply_lighting_preset", "lighting_apply"}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in accepted_names:
            lighting_fn = node
            break

    assert lighting_fn is not None, "lighting apply endpoint function not found in main.py"

    # Check that the hub.broadcast_system_event call is inside an if-hub guard
    # We do this by looking for an If node that tests `hub is not None` or `hub`
    # and contains the broadcast call
    hub_broadcast_guarded = False
    for node in ast.walk(lighting_fn):
        if not isinstance(node, ast.If):
            continue
        # Check the test condition references 'hub'
        condition_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
        if "hub" not in condition_src:
            continue
        # Check the body contains broadcast_system_event
        body_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
        if "broadcast_system_event" in body_src:
            hub_broadcast_guarded = True
            break

    assert hub_broadcast_guarded, (
        "REG-002 REGRESSION: lighting apply endpoint calls hub.broadcast_system_event "
        "without a null guard. This will raise AttributeError when hub is None."
    )


# ─────────────────────────────────────────────────────────────────────────────
# REG-003: internal-nudge / bot feedback loop guard
# ─────────────────────────────────────────────────────────────────────────────

def test_reg003_internal_nudge_does_not_trigger_room_wide_echo(tmp_path):
    """REG-003: internal nudges stay private and cannot recursively trigger bots."""
    import asyncio
    from modules.bots import BotManager
    from modules.hub import Hub
    from modules.models import BotConfig, BotProvider

    async def exercise():
        hub = Hub(tmp_path)
        manager = BotManager(tmp_path, hub)
        manager.upsert_config(BotConfig(
            bot_id="cast-test", name="Cast Test", provider=BotProvider.OLLAMA,
            model="no-model-called", api_key_env="UNUSED_TEST_KEY", rooms=["world"],
        ))
        scheduled = []

        async def record_target(session, payload):
            scheduled.append((session.config.bot_id, payload["text"]))

        # Current voluntary invitations use request_turn, not the normal chat
        # scheduler. Mock that boundary so this privacy test cannot call a model.
        invited = []
        async def record_invitation(bot_id, room, hint, *, actor, required):
            invited.append((bot_id, room, hint, actor, required))
            return {"state": "declined"}
        manager.request_turn = record_invitation
        manager._schedule_reply = record_target
        hub.on_chat_callback = manager.on_chat_message

        assert await manager.nudge("world", "One quiet private direction")
        assert invited == [("cast-test", "world", "One quiet private direction", "system:jeremy", False)]
        assert scheduled == []  # declining a voluntary invitation creates no speech
        assert await hub.get_recent_history("world") == [], "Private stage direction leaked into chat log"

        await hub.post_chat_message("world", "__internal_nudge__", "Current private direction")
        await manager.on_chat_message({
            "room": "world", "user_id": "conductor",
            "text": "Private stage direction", "nudge": True,
        })
        assert scheduled == []
        assert len(invited) == 1

        await hub.post_chat_message("world", "visitor", "Hello, cast")
        assert scheduled == [("cast-test", "Hello, cast")]

    asyncio.run(exercise())


# ─────────────────────────────────────────────────────────────────────────────
# Additional regression: bot self-reply guard in BotManager
# ─────────────────────────────────────────────────────────────────────────────

def test_reg003b_bot_manager_has_self_echo_guard():
    """BotManager.on_chat_message must skip messages where sender == this bot.

    Without this guard, a bot's own reply triggers another reply → infinite loop.
    """
    bots_py = (ROOT / "modules" / "bots.py").read_text(encoding="utf-8")
    # The guard: `if user_id == bot_uid: continue`
    assert "user_id == bot_uid" in bots_py or "user_id == self.bot_user_id" in bots_py, (
        "BotManager is missing the self-echo guard. Bots will reply to their own messages."
    )


def test_reg003c_bot_manager_has_bot_to_bot_guard():
    """BotManager must skip messages from other bots unless directly mentioned."""
    bots_py = (ROOT / "modules" / "bots.py").read_text(encoding="utf-8")
    assert 'startswith("bot-")' in bots_py or "startswith('bot-')" in bots_py, (
        "BotManager is missing the bot-to-bot chatter guard."
    )
