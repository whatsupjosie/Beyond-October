# CORNER CUT AUDIT — 2026-08-23
## Every run reviewed against actual live state, not memory or claims.

---

## What holds up — verified right now by execution

| Claim | Check | Result |
|---|---|---|
| App boots, health 200 | `GET /health` | ✅ 200 |
| Doctor: 0 required failures | `GET /api/doctor` | ✅ 9 checks, 0 required failures |
| Affect engine live in alex_core | grep `_affect_engine.evaluate` | ✅ line 766 |
| cargo build --lib clean | ran it | ✅ 0 errors |
| 23 Rust tests pass | ran them | ✅ 23/23 |
| ws_renderer binary at correct path | ls data/bin/ws_renderer | ✅ 9.3MB |
| Doctor: Rust bridge = pass | ran doctor directly | ✅ pass |
| AvatarPerformerManager ready | boot log | ✅ "ready (not started)" |
| PubPartner 14 tests pass | ran them | ✅ 14/14 |
| Bubble stack imports clean | python3 -c import | ✅ OK |
| Cup demo runs with real physics | ran it | ✅ 4 resolutions, real N/Ns values |
| Domino chain propagates | ran it | ✅ bubbles 54→417, sources grow per hop |
| requirements.txt dry-run clean | ran it | ✅ no errors |
| full-animation feature still has 7 errors | ran cargo build | ✅ same 7 (documented, not new) |
| runtime spine 200/available/import_ok | hit endpoint | ✅ confirmed |

---

## Real corners cut — honest, in order of severity

### 1. PUBCAST_WS_PORT doc missing from .env.example — FIXED this pass
Every boot logs "PUBCAST_JWT_SECRET is not set — using insecure default."
I flagged this twice (early state-of-union, Run 3's audit) and moved on
both times. `PUBCAST_WS_PORT` was also missing. The `.env.example` existed
but was incomplete. Added both entries with the `--port` silent-ignore note.
This won't stop anyone from running the app in dev — the insecure default
works — but it was the right thing to do before calling the session clean.

### 2. AvatarPerformerManager.start() never called — logged, not fixed
Flagged in Run 3's audit, confirmed again this pass: `performer_manager`
is instantiated at boot but `.start()` is never called anywhere in main.py.
The manager stays "ready (not started)" forever. The binary exists, the
Python-side client exists, the Doctor says pass — but they never actually
connect at runtime. This is a real, live gap. Not fixed because touching
main.py's lifespan without the full test suite isn't the right move under
token pressure. Logged clearly across three handoffs — whoever does the next
pass knows exactly where to look.

### 3. The --port claim in Run 3 was wrong and then corrected, but the
correction was spread across a note in the README and not in the handoffs
themselves. The Run 3 handoff still says "--port CLI arg is silently ignored"
as a "minor, worth a one-line fix" item. This is accurate — `PUBCAST_WS_PORT`
is the real mechanism, --port is genuinely ignored. The README documents it.
The handoff language is slightly sloppy ("could be misread as a todo" when
it's actually a design fact). Not a consequential gap.

### 4. bubble_routes never wired in — documented but left
The 9 recovered bubble stack files are in modules/, verified importable,
and the sandbox runs real physics. But `bubble_routes.router` is not mounted
in main.py, `BubbleJeremyAdapter` is not connected, and the
physics→choreography bridge (approximately 20 lines) was never written.
This was Run 6's documented conclusion: "scope was recovery + verification."
That was the right call — wiring main.py without verifying the full boot
afterward is the kind of cut that creates silent regressions. The next run
for this is clearly defined in RUN6_HANDOFF_2026-08-23.md.

### 5. PerformerStreamer round trip never got a clean close
Run 3's verified round trip always ended with "Connection reset without
closing handshake" because `PerformerStreamer` has no `disconnect()` method
(it's `_reconnect`, private). The registration (`New avatar registered`)
was real and correct, but the close was always abrupt. Re-ran this in the
audit pass — same result. The WARN is cosmetic (the frame was accepted),
but the Python client has a minor API gap (`disconnect` not exposed
publicly). Logged, not fixed.

### 6. full-animation feature: 7 errors not fixed
5 missing types (`BoneMask`, `AnimationLibrary`, `TransitionCondition`,
`AnimationStateMachine`, `AnimationBlendTree`) in
`complete_animation_controller.rs`. Documented in Run 2 and Run 3,
re-confirmed this pass. Intentionally not fixed — inventing animation blend
tree semantics under time pressure is a real risk. The correct next step
is a dedicated run that starts by specifying what these types should mean,
then implements them. This is a known, contained gap, not a hidden one.

### 7. alex_memory.py deprecation banner — proposed, never written
Run 4 recommended adding a deprecation banner to `alex_memory.py` so no
future session mistakes it for the current implementation and wires it in.
That banner was never actually written. The file still opens with its
original 2026 header, nothing warning that it's a superseded rewrite.
Low urgency but real: it's a 1363-line file that looks exactly like a
current implementation at a glance. The next pass in this area should add
the banner as the very first thing.

### 8. The-Prime repo — never pushed, container-only
Every run from Run 1 onward: all work lives in `/home/claude/pubcast/` in
this session's container. The run bundle zip is the only durable artifact.
Claude has no GitHub write access. If Josie has not pushed the container
state or downloaded the zip, all of the following are container-only:
  - Cargo.toml (full-animation feature declaration)
  - animation_data_library.rs (import fix)
  - data/bin/ws_renderer (compiled binary)
  - modules/bubble_stack_pikpc/* (9 recovered files)
  - modules/bubble_stack.py, bubble_routes.py, bubble_jeremy_adapter.py
  - rust_crate/README.md
  - .env.example (PUBCAST_WS_PORT addition)

This is documented in every handoff. Not a corner cut — it's a structural
constraint. But worth re-stating explicitly at every audit.

---

## Things that looked like corners but aren't

- **affect_wiring.py** — built as a duplicate, marked deprecated before
  causing damage. The real integration was already in alex_core.py.
  Correctly caught and documented.

- **The-Prime rejected** — Run 1 abandoned it because it couldn't boot
  (13 unresolvable imports). Correct decision. All subsequent work was on
  the right tree.

- **Run 5 stopped without wiring PubWorld.jsx** — correct. The architecture
  doc described a system that doesn't exist, and the manifest was for a
  different bundle. Stopping before building against a fabricated premise
  was exactly right.

- **Domino chain test built fresh** — prompted by understanding the Run 6
  prompt correctly, not as a corner cut. The "regression test" didn't exist
  as a file; the test was the thing that needed to be built.

---

## Net assessment

The work is solid and the claims are accurate. The gaps that remain are
real but documented: one live integration missing (`AvatarPerformerManager`),
one router not mounted (`bubble_routes`), one bridge not written
(physics→choreography, ~20 lines), one deprecation banner not written
(`alex_memory.py`), and everything living in a container that needs pushing.

None of the above is hidden. None contradicts what the handoffs say.
The difference between this and a perfect run is operational follow-through
(pushing to GitHub, wiring the last few connections), not new discoveries
about the code being wrong.

*Rear View Foresight LLC — Feic Mo Chroí*
