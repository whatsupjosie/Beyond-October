"""Local PubPartner activation smoke test.

Run from the project root:
    python scripts/pubpartner_smoke.py

This does not need cloud keys. It proves the local friend loop can create a
session, store guidance, run a mock provider turn, restore exact source, and
verify receipts.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.pubpartner_core import PubPartnerSpine


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pubpartner_smoke_") as tmp:
        spine = PubPartnerSpine(Path(tmp))
        launch = await spine.launch_check()
        if not launch.get("ok"):
            print(json.dumps({"ok": False, "stage": "launch_check", "launch": launch}, indent=2))
            return 1
        await spine.create_session(user_id="smoke", session_id="on", friend="alex", provider="mock", project_id="pubpartner", room_id="phone")
        spine.add_guidance(user_id="smoke", friend_id="alex", project_id="pubpartner", text="For exact text, restore before quoting.", priority=9)
        result = await spine.run_turn(user_id="smoke", session_id="on", message="Chorus:\nDo not change this line.", content_kind="lyrics")
        source_id = result["source"]["id"]
        restored = spine.restore_source(user_id="smoke", session_id="on", source_id=source_id)
        receipts = spine.list_receipts(user_id="smoke", session_id="on")
        ok = result.get("live_loop") is True and restored["text"] == "Chorus:\nDo not change this line." and receipts["verify"]["ok"] is True
        print(json.dumps({
            "ok": ok,
            "friend_response": result.get("friend_response"),
            "source_id": source_id,
            "receipt_verify": receipts.get("verify"),
            "token_comparison": result.get("token_comparison"),
        }, indent=2, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
