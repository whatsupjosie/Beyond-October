from __future__ import annotations

import asyncio
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.alex_core import AlexCore
from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.session_resurrector import SessionResurrector


def test_session_resurrector_warms_current_alex_bridge(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)
    alex = bridge.alex_for("memory-user")
    asyncio.run(alex.process_message("I am building persistent memory for the studio", typing_speed=80))

    resurrector = SessionResurrector(alex=alex, bridge=bridge, data_dir=tmp_path)
    context = asyncio.run(
        resurrector.resurrect(
            user_id="memory-user",
            session_id="session-resume",
            project_id="proj",
            room_id="waiting_room",
        )
    )

    assert context.memory_count >= 1
    assert context.packet["resumed_from_memory"] is True
    assert "Session resumed" in context.whisper
    assert "What I remember about you" in context.whisper
    assert "prior Alex memory" in bridge.jeremy_whisper(
        user_id="memory-user",
        session_id="session-resume",
    )

    bridge.shutdown()
