# Codex Foundation Wiring Status - 2026-06-14

## Scope
Checked and strengthened the Codex construction build foundation for the next PubCast systems layer. Work stayed inside the copied construction build in Big Zip.

## Completed
- Kept BlackBox as an external witness package, not a player-menu or in-game route surface.
- Confirmed no `blackbox_witness`, `blackbox_status`, or `/api/blackbox` exposure exists in `main.py` or `config/menu_coverage.json`.
- Added `modules/ai_runtime_slots.py` for named Alex/Jeremy model-slot status without starting models.
- Added disabled Ollama candidate profiles in `config/ai_runtime.json`:
  - `ministral_3b_local` -> `ministral:3b`
  - `gemma4_e4b_q4_local` -> `gemma4:e4b-q4`
- Added the `AI / Conversation` menu section for Alex, Jeremy, conversation router, EVO, EQ, and model slots.
- Added `/api/ai/model-slots` read-only status route.
- Extended Pub Manager raw status to include `conversation_ai`, `alex`, `jeremy`, `evo`, `eq`, and `model_slots`.
- Extended Pub Manager recovery actions with `ai.model_slots`.
- Hardened `modules/ai_runtime.py` to read AI JSON configs with `utf-8-sig`, because Windows BOM output can otherwise break JSON loading.

## Validation Run
- Syntax check passed for `main.py`, `modules/pub_manager_recovery.py`, `modules/ai_runtime.py`, and `modules/ai_runtime_slots.py`.
- Model-slot direct check passed:
  - Alex slot: `ministral_3b_local`, available, disabled.
  - Jeremy slot: `gemma4_e4b_q4_local`, available, disabled.
- Pub Manager recovery direct check passed: disabled model slots produce `ai.model_slots` suggestion.
- External BlackBox checks passed:
  - `tools/blackbox_smoke.py`
  - `tools/blackbox_hardening_check.py`

## Deliberately Not Activated
- No Ollama models were started.
- No model profile was enabled.
- BlackBox was not added to player menus.
- BlackBox was not given in-game browse/decode/admin routes.
- Full pytest was not used because the construction environment is missing `starlette`, and the web test harness imports it from `tests/conftest.py`.

## Next Best Pass
- Confirm the exact local Ollama tags for Ministral/Mistral 3B and Gemma E4B Q4.
- Decide which runtime component owns the append-only BlackBox recorder instance during broadcast startup.
- Once the runtime spine/event bus is ready, wire BlackBox as append-only event output only, with offline review remaining outside the game UI.