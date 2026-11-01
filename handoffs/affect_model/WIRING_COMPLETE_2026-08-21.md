# AFFECT ENGINE — WIRED AND VERIFIED
## 2026-08-21

Executed the prompt from CONTINUE_FROM_HERE/NEXT_THREE_PROMPTS.md, prompt 1.
All five steps done and verified against the real running app, not the
standalone demo. One deliberate deviation from the prompt's literal wording,
explained below — following the evidence over the guess.

---

## THE REAL INTEGRATION POINT (corrected from the prompt's guess)

The prompt suggested starting in `modules/bots.py` and
`modules/room_conductor.py`. Once actually opened, those turned out to be the
**character chat completion path** — Pete, RePete, Sir Purfluous talking
through Anthropic/OpenAI. That's a separate system from Alex's emotional
state machinery entirely.

The real point, found by reading `alex_jeremy_bridge.py` first (per the model
doc's own section 6, which names `jeremy_whisper()` in that exact file as the
consumer): `AlexJeremyBridge` never sees user text. It only reads
`alex._current_state` and `alex._user_battery`, both already computed. So the
actual per-turn text ingestion has to be — and is — inside `AlexCore.
process_message()` in `alex_core.py`, reached live via the mounted
`POST /api/alex/message` route in `alex_routes.py`.

That's where everything was wired.

---

## WHAT WAS DONE

### 1. Engine call — `modules/alex_core.py`
- Module-level singleton `_affect_engine = AffectContextEngine()`, shared
  across all users (the engine already partitions internally by user_id).
- Called inside `process_message()`, **after** `_analyze_input()` and
  `_update_ai_state()` — the existing keyword/threshold safety pass (stress
  words → `ANCHOR`, grounding anchors) runs completely unmodified, first,
  unconditionally.

### 2. Legacy bridge, with a safety guard the prompt didn't specify
`to_legacy_battery()` is called and applied — **but only when the current
state is not already `ANCHOR` or `WITNESS`.** This guard wasn't in the
original prompt; I added it after actually reading `_update_ai_state()` and
finding it drives real crisis behavior (grounding anchors, breathing
exercises). The nuanced engine's maturity/confidence gating is correct for
everyday reads, but must never be the only thing standing between a
cold-start stranger and a crisis response. `observing` already returns
`None` from `to_legacy_battery()` by design — this guard is on top of that,
not a replacement for it.

### 3. `meet_them_at` → system prompt guidance
`response_guidelines['operating_note']` — additive field, sitting alongside
the existing `tone`/`approach`/`complexity`/`interaction` keys without
touching any of them, including the `ANCHOR`/`WITNESS` safety blocks.

Propagated onward: `alex_jeremy_bridge.py`'s `_packet_from_alex()` now reads
`alex._last_affect_reading` and additively enriches the packet with
`meet_them_at`, `affect_state`, `baseline_quality`, `doubt_attaches_to`.
`jeremy_whisper()` appends `meet_them_at` to its output when present. Every
existing field in both functions is untouched.

### 4. Persistence
`data/affect/{user_id}.json` — flat file, atomic write (same
temp-file-then-replace pattern already used by `save_state_snapshot()`).
Loaded in `__init__`, saved every turn via a hook into
`save_state_snapshot()` (already called at the end of every `process_message`).

### 5. End-to-end proof — against the real app, twice

**Live conversation, 16 real turns through `POST /api/alex/message`:**
cold start correctly reported "not enough history" for six turns, crossed the
maturity gate, then the register genuinely shifted from "Short answers" to
"Direct answers" as the actual message content changed shape mid-conversation
— not scripted, a real classification response to real content.
`user_battery` legitimately transitioned `medium → low → charged`, proving
the legacy bridge is actually taking effect.

**Persistence, proven the only way that counts:** killed the process
(`pkill -9`), confirmed it was dead, cold-started PubCast fresh, sent one more
message as the same `user_id`. Result: `ai_state: companion`,
`operating_note: "Keep it quick. Direct answers. They state; confirm or
correct."` — not the cold-start message. The baseline survived a real
restart.

---

## WHAT THIS DOES NOT COVER (stated plainly, not left implicit)

**`bots.py`'s character chat is not wired to this.** Pete, RePete, Sir
Purfluous talking through `/api/bots/{id}/chat` do not receive
`operating_note` or any affect reading. That pipeline calls Anthropic/OpenAI
directly and has no connection to `AlexCore` at all. Whether it should — Pete
adapting to how the user is actually operating right now, the same way
Jeremy's whisper does — is a real, separate question. Not answered here,
not silently assumed.

**Scoring logic inside `affect_context_engine.py` was not touched.**
Confirmed by diff-free import — only called, never edited.

---

## FOR THE NEXT SESSION

If the bot chat path should also receive this, the shape is already proven:
read `AlexJeremyBridge.current_packet(user_id, session_id)` — the same packet
Jeremy already reads — and pull `meet_them_at` into whatever assembles the
system prompt for Pete/RePete/Sir Purfluous. The packet already carries it;
nothing new needs to be computed.

That's prompt 2's territory (memory) touching prompt 1's territory (affect) —
worth naming as a real dependency the next session should know about rather
than discover independently.
