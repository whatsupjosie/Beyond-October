# RUN 1 HANDOFF — 2026-08-23

## Headline: Run 1 was already done. I verified it rather than rebuilding it.

Run 1's premise was "the affect engine is called from NOWHERE in the live app."
**That premise was wrong.** `alex_core.py` already contains a complete, live
integration — and a better one than Run 1 specified. I found this by tracing
the actual call path instead of trusting the premise, verified it with a real
16-turn conversation, and stopped rather than building a duplicate.

**No production code was changed this run.** That is the correct outcome.

---

## What I traced, and what I found

### The route in the prompt does not exist
Run 1 said to test through `/api/bots/{id}/chat`. That route exists in **no**
main file. Grep across `main.py`, `main_temp.py`, `main_comprehensive.py`
returns only `/api/bots`, `/api/bots/say`, `/api/bots/{bot_id}` (DELETE),
`/api/bots/reload`. The route name came from a stale session summary. This is
exactly the "some names from past sessions may be stale" hazard the prompts
warn about — it was in my own prompt.

### Which main is live
`README.md` says `uvicorn main:app`. The repo's own audit
(`FIVE_ROUND_THREE_SOLUTION_REPORT_2026-04-25.md`) calls `main_temp.py` and
`main_comprehensive.py` "shadow mains." `COMPREHENSIVE_HANDOFF.md` instructs
`cp main_comprehensive.py main.py` — i.e. it was **never deployed**.
**`main.py` is the live entry point.**

### The real integration, already present in alex_core.py

| Run 1 step | Already implemented at | Notes |
|---|---|---|
| 1–2. evaluate() at ingestion | `alex_core.py` ~line 766, inside `process_message` | `_affect_engine.evaluate(text, user_id, session_id)` |
| 2. result reachable by reply path | `self._last_affect_reading` | instance attr, read later in same method |
| 3. battery override, None-guarded | ~lines 769–771 | `if suggested is not None:` — the exact invariant Run 1 specified, already honored |
| 4. `meet_them_at` → prompt | ~line 796 | `response_guidelines['operating_note']` |
| 5. persistence | `_load_affect_state` (line 545, in `__init__`) / `_save_affect_state` (line 657, on every snapshot) | via **MemoryCore**, not flat files |
| 6. proof | done this run — see transcript below | |

**Plus a safety guarantee Run 1 didn't even ask for** (line 768): the affect
reading is *not permitted* to move state out of `ANCHOR`/`WITNESS`. A
confident "they're fine" read cannot pull someone out of a crisis response.

### alex_core explicitly supersedes affect_wiring.py
`_affect_state_path()` is commented *"DEPRECATED — kept only so a stray
Prompt-1-era file gets migrated once."* `_save_affect_state` says *"No longer
writes to the Prompt 1 flat file."* The codebase already moved past the
flat-file approach that `affect_wiring.py` (written earlier the same day)
implements.

---

## Verified evidence — 16-turn run through `AlexCore.process_message`

Cold start, `/tmp/run1_alex` wiped first. Real code path, not a mock.

```
#   state      conf   battery    ai_state     operating_note
1   observing  0.00   medium     guide        Not enough history yet — answer plainl
2   observing  0.00   medium     guide        Not enough history yet — answer plainl
3   observing  0.00   medium     guide        Not enough history yet — answer plainl
4   observing  0.12   medium     guide        Not enough history yet — answer plainl
5   observing  0.11   medium     guide        Not enough history yet — answer plainl
6   observing  0.09   medium     guide        Not enough history yet — answer plainl
7   observing  0.08   medium     guide        Keep it quick. Direct answers. They st
8   observing  0.07   medium     guide        Keep it quick. Direct answers. They st
9   observing  0.06   medium     guide        Keep it quick. Direct answers. They st
10  flow       0.36   charged    guide        Keep it quick. Direct answers. They st
11  flow       0.40   charged    guide        Keep it quick. Direct answers. They st
12  flow       0.44   depleted   witness      Keep it quick. Direct answers. They st
13  flow       0.48   depleted   witness      Keep it quick. Direct answers. They st
14  flow       0.52   depleted   witness      Keep it quick. Direct answers. They st
15  flow       0.56   depleted   witness      Keep it quick. Direct answers. They st
16  friction   0.60   depleted   witness      Keep it quick. Direct answers. They st

--- persistence check ---
MemoryCore.load_affect_state() -> baseline n=16 observations
baseline keys: ['alpha', 'mean', 'n', 'var']
```

Reading this honestly:
- Confidence matures 0.00 → 0.60 across 16 turns. Consistent with the model's
  documented ~12-turn maturity requirement.
- `operating_note` populated on every turn — step 4 confirmed working.
- **Turn 12 is the safety guard firing.** Legacy analysis drops battery to
  depleted → `WITNESS`. The affect engine is simultaneously reading `flow`
  (0.44) and *wants* to set battery `charged`. The guard blocks it. Exactly
  the intended behavior, observed live.
- Persistence confirmed: n=16 through MemoryCore, not flat files.

Test script: `test_run1_live.py` in repo root (safe to delete; it's a harness,
not production code).

---

## What I changed

**One file, non-functional:** added a deprecation header to
`modules/affect_wiring.py` warning against wiring it in. I did not delete it —
it's in the run bundle Josie already has, and silent deletion would be
confusing. The header explains where the real integration lives.

**Nothing else.** No production code touched.

---

## Logged, NOT fixed (per Run 1's instruction to log rather than fix)

1. **`main.py` never sets `hub.on_chat_callback`.** Both shadow mains do it at
   line 555 (`hub.on_chat_callback = bot_manager.on_chat_message`); `main.py`'s
   `lifespan()` does not. **In the live app, bots do not auto-reply to chat.**
   This is a significant pre-existing gap, unrelated to affect wiring. Worth
   its own focused run.

2. **`room_conductor.process_conversation_turn()` has zero callers** despite
   its docstring calling itself "Top-level entry point for each conversation
   turn." Dead entry point.

3. **Possible affect model accuracy issue.** Turns 10–15 ("maybe I'm
   approaching this wrong" / "I'm tired" / "whatever, doesn't matter") read as
   `flow` with rising confidence. Intuitively that looks like friction or
   exhaustion, not flow. Only turn 16 flips to `friction`. This is *scoring
   logic*, which Run 1 explicitly forbade touching — so it is logged, not
   touched. **Recommend a dedicated run to validate model accuracy against
   labeled transcripts.** Note the safety guard meant this misread caused no
   harm here, which is the design working.

4. `AffectContextEngine` is a **module-level singleton** in `alex_core.py`
   (line 447) shared across all `AlexCore` instances, partitioned internally by
   user_id/session_id. Looks intentional (there's a comment to that effect at
   line 444) but worth confirming under concurrent multi-user load.

---

## Impact on the remaining nine runs

- **Run 1: CLOSE IT.** Done, verified. Don't spend Opus on it.
- **Run 4 (memory unification): significantly reduced.** Its main deliverable —
  "migrate affect PersonalBaseline/PersonalPrior into the canonical store" — is
  **already done** (MemoryCore). Run 4 still has value for auditing the *other*
  memory modules, but drop the affect-migration portion and re-scope. Sonnet is
  probably now sufficient.
- **New candidate run:** wire `hub.on_chat_callback` in `main.py` so bots
  actually respond in the live app. This may matter more than several existing
  runs — right now the live server's bots are silent.
- **Runs 2/3 (Rust) unaffected.** Still the right next move.

---

## The meta-lesson worth keeping

I built `affect_wiring.py` earlier today from a session summary saying the
engine wasn't wired. I never checked `alex_core.py` first. The prompts I then
wrote inherited that same unverified assumption and would have had a future
session wire in a duplicate, competing persistence path — the exact "eighth
memory system" failure Run 4 warns against.

The instruction that caught this was *"grep, not memory of past session
summaries."* It should stay at the top of every future run prompt. Trace the
call path before writing the fix.

*Rear View Foresight LLC — Feic Mo Chroí*
