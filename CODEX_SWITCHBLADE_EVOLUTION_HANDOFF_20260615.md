# Codex Switchblade Evolution Handoff - 2026-06-15

## Current Switchblade Shape

- Alex creative/dialogue blade: `ministral_3b_local` -> `ministral-pubcast:3b` (`Q4_K_M`).
- Jeremy live support blade: `gemma3_1b_q4_local` -> `google_gemma-3-1b-it-Q4_K_L:latest`.
- Background math/process blade: `gemma4_compute_q5_e2b_local` -> `gemma4-compute-q5:e2b`.
- Background fallback: if E2B fails, the bridge falls back to `gemma3_1b_q4_local`.

## New Upgrade Added

Added Auto Switchblade routing:

- `auto`, `switchblade`, or `router` roles can now choose a slot before calling a model.
- Creative/dialogue terms route to Alex/Ministral.
- Support/help terms route to Jeremy/1B Q4.
- Math/technical/debug/status terms route to background_math/E2B.
- Responses include a `switchblade` object with requested role, chosen role, slot, mode, reason, and confidence.
- Fallback use is reported with `fallback_used: true` and the primary error remains visible.

## Files Added Or Changed

- `modules/switchblade_router.py`
- `modules/pub_partner_chat.py`
- `modules/ai_runtime_slots.py`
- `config/ai_runtime.json`
- `static/pub_partner_chat.html`
- `tests/test_pub_partner_chat.py`
- `tests/test_ai_runtime_slots.py`

## Validation

Focused tests pass:

```text
12 passed
```

## Next Refinements

1. Add model-health memory so a blade that recently timed out is skipped briefly.
2. Track latency per profile and prefer faster blades when confidence is close.
3. Add explicit Switchblade policy modes: speed, quality, private, background, filming.
4. Add per-room/per-scene routing rules later, once more PubCast systems are wired.
5. Add a lightweight queue for background E2B so live chat never waits on slow background work.

## Known Concern

E2B can be slow on CPU and may fail empty after a long wait. The fallback works, but the next hardening pass should skip or shorten E2B when it has recently failed.