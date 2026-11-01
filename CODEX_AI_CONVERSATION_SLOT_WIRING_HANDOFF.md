# Codex AI Conversation Slot Wiring Handoff

Date: 2026-06-14
Root: C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614

## What changed
- Added modules/ai_runtime_slots.py to define Alex and Jeremy model slots without starting models.
- Added disabled Ollama candidate profiles:
  - ministral_3b_local -> ministral:3b
  - gemma4_e4b_q4_local -> gemma4:e4b-q4
- Added the AI / Conversation menu section for Alex, Jeremy, conversation routing, EVO, EQ, and model-slot status.
- Added tests for model-slot declaration and the menu boundary.
- Completed external-only BlackBox file/spec handoff.

## BlackBox boundary
BlackBox is copied into the construction build as an external witness package, but it is not in the player menu and no in-game BlackBox route was added in this pass.

## Safety notes
- Backups of edited construction files are in $backupDir.
- No dependencies installed.
- No models started.
- No source outside the construction copy was edited.
