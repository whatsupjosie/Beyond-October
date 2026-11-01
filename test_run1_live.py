"""
Run 1 verification — 15+ turn conversation through the REAL integrated path.

NOT through affect_wiring.py (which turns out to be redundant), but through
AlexCore.process_message(), which is where the affect engine is actually
wired in the live app.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.alex_core import AlexCore, _HAS_AFFECT_ENGINE


TURNS = [
    "Morning. Starting on the renderer integration today, feeling good about it.",
    "Got the crate cloned and the deps resolved already, faster than I expected.",
    "OK, first compile attempt. Let's see what happens.",
    "Hmm, 14 errors. Mostly missing trait impls I think.",
    "Fixed eight of them. The other six are all in the same module.",
    "This one's weird. It's complaining about a lifetime I didn't write.",
    "Been on this single error for about forty minutes now.",
    "I don't actually understand what the borrow checker wants here.",
    "Tried three different things, none of them worked.",
    "Maybe I'm approaching this whole thing wrong.",
    "It's been two hours on what should have been a ten minute fix.",
    "I'm tired. Not sure I'm thinking clearly anymore.",
    "Everything I try just makes it worse honestly.",
    "Whatever. Doesn't matter. I'll just comment the whole module out.",
    "Actually no. Let me just stop and come back to it tomorrow.",
    "Thanks for sitting through that with me.",
]


async def main():
    print(f"Affect engine available: {_HAS_AFFECT_ENGINE}")
    if not _HAS_AFFECT_ENGINE:
        print("FAIL: affect engine did not import — cannot verify")
        return

    alex = AlexCore(user_id="run1_test_user", data_dir=Path("/tmp/run1_alex"))
    print(f"AlexCore initialized. Starting battery: {alex._user_battery.value}\n")
    print(f"{'#':<3} {'state':<10} {'conf':<6} {'battery':<10} {'ai_state':<12} operating_note")
    print("-" * 100)

    for i, text in enumerate(TURNS, 1):
        resp = await alex.process_message(
            text,
            metadata={"session_id": "run1_session"},
        )
        reading = (alex._last_affect_reading or {}).get("reading", {})
        state = reading.get("state", "-")
        conf = reading.get("confidence", 0.0)
        note = resp.get("response_guidelines", {}).get("operating_note")
        note_s = str(note)[:38] if note else "-"
        print(f"{i:<3} {state:<10} {conf:<6.2f} {resp['user_battery']:<10} "
              f"{resp['ai_state']:<12} {note_s}")

    print("\n--- persistence check ---")
    alex.save_state_snapshot()
    saved = alex.memory.load_affect_state()
    if saved:
        n = saved.get("baseline", {}).get("n", 0)
        print(f"MemoryCore.load_affect_state() -> baseline n={n} observations")
        print(f"baseline keys: {sorted(saved.get('baseline', {}).keys())[:6]}")
    else:
        print("No affect state persisted (load_affect_state returned None)")


if __name__ == "__main__":
    asyncio.run(main())
