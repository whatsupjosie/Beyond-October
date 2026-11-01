# Pete / Alex Bourgeois — Bot baseline

**Canonical identity:** Alex Bourgeois, commonly called Pete. **Performer:** PubPartner Alex (a different identity/memory scope). **Character ID:** `pete` (existing ID preserved).

## What works

- Existing PubCast BotManager room and private character-chat integration.
- Offline deterministic, hand-authored Pete responses available using `settings.offline_character` in `data/bots/pete.json`. No external LLM required. The provider result in private chat is tagged `offline_character`.
- Character knowledge: name and nickname, career, Purfluous, RePete, studio operations, safety, simple greetings. This is **not general conversational intelligence**.
- Full earlier Pete personality/backstory remains in `modules/character_profiles.py` and is enriched into the model prompt if offline mode is turned off.
- No import of PubPartner Alex's personal conversational history into Pete's memory. They are separate.
- `assets/avatar/cast/pete/reference/` contains accepted 2D visual references for upcoming art production; these images do not constitute a rigged 3D skin. The existing shipped Pete GLB is a separate provisional asset and **has not been changed**.

## Connecting a real model later

`settings.offline_character` now defaults to `false`: the configured model is attempted first. Supply the provider credentials and restart/reload bots. `offline_fallback` defaults to `true`, so an unavailable model returns limited, authored dialogue. This is not equivalent to a successful AI conversation. Character memory is not merged with PubPartner private memory by this toggle.

## Verification

`python -m pytest -q tests/test_pete_character_offline.py tests/test_ai_characters.py tests/test_alex_personality_continuity.py`

Known limitations: deterministic dialogue covers a small set of subjects; no generative personality nuance without a model; character-specific episodic autobiographical memory and real PubPartner-as-performer routing remain to be commissioned; GLB mesh/weights/animations need separate real modeling.
