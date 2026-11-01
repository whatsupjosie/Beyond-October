# BlackBox External Access Boundary

Date: 2026-06-14

BlackBox files are present in this construction build as an external witness package, not as a player-menu feature.

## Boundary
- Do not expose BlackBox review, decode, delete, edit, or administrative controls inside the player menu.
- Do not add in-game routes that let normal gameplay surfaces browse or alter BlackBox records.
- Runtime integration should be append-only recording only, when explicitly wired later.
- Review and decoding should be performed outside the game UI through offline tools or a separately opened operator process.

## Current files
- lackbox_event_language/
- lackbox_recorder/
- lackbox_decoder/
- 	ools/blackbox_smoke.py
- 	ools/blackbox_hardening_check.py
- 	ests/test_blackbox_event_language.py
- BLACKBOX_EVENT_LANGUAGE_SPEC.codex_construction.md

## Rationale
The BlackBox is meant to be the impartial flight recorder. Keeping review access outside the game lowers the chance that player-facing systems, avatars, menus, or scene scripts can tamper with witness records.
