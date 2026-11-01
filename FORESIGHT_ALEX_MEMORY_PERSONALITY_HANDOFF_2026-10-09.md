# Foresight — Alex Memory & Personality Priority Pass

**Base:** `PubCast_Foresight_FOUR_ROUND_DEBUGGED_2026-10-09.zip`

## Acceptance condition
Alex's identity and owner-editable personality must remain recognizable when models change or the program restarts. Past user turns must be stored, selectively recalled, and actually provided to the response generator. Private memories cannot leak into shared rooms or other users' prompts. The interface must not mislabel a simulated response as Alex's live speech.

## Changes in the canonical Foresight program

1. **Single lasting personality.** `modules/pubpartner_core.py` now merges the persisted Alex friend profile and vessel identity, instead of falling back to the smaller vessel voice when no explicit profile is supplied. `create_session` and `build_turn_packet` use the same resolution. `FriendProfile.compact` carries the vessel's self-concept to the speaking prompt, including explicit `friend='alex'` selection.
2. **Speaking path corrected.** `modules/pubpartner_provider.py` uses one provider-independent generation contract for Ollama, hosted providers, and OpenAI-compatible endpoints. The provider generates the selected friend's direct reply using the FCP1 friend/memory/history profile; it is not instructed to avoid speaking as Alex. The LLM remains swappable while Alex's voice contract remains program-owned.
3. **True recent conversational continuity.** On omitted history, private PubPartner turns recover up to four successful, real-model exchanges from the **existing** per-user session ledger and VerbatimVault. This survives service restart and avoids a second memory/transcript database. Explicit `history=[]` is respected. Failed, mock, echo, and offline diagnostic turns are not brought back as prior AI conversations. This auto-history is within a given session ID, not across arbitrarily new session IDs.
4. **Open-ended owner recall.** The Alex/Jeremy Bridge can answer explicit requests such as "What do you remember about me?" from its durable owner diary, including entries older than the seven-day recent cache; ordinary topical questions still require relevance matching. Bounded and excluded from shared packets.
5. **Room privacy.** A task field claiming `audience='private'` does not turn a shared lobby into a private channel. The access classification is constrained by the real room type.
6. **Local context window.** The previous hard-coded Ollama 2,048-token context is inadequate even for the initial complete Alex prompt (measured at ~2,367 estimated tokens before generation). Ollama context is now budgeted between 4,096 and 8,192 tokens by default for PubPartner with override support; the transport accepts `num_ctx`. It warns when configured capacity is inadequate. Larger windows can require more RAM.
7. **No more fake friend by default.** `static/pubpartner.html` selects Ollama rather than Mock Test; offline fallback is opt-in and clearly marked. `static/pubpartner.js` labels unavailable providers and diagnostic responses rather than drawing them as Alex's real reply. If the untouched example model is missing, it selects an installed Ollama model discovered by the existing provider-status query. Hosted models can still be selected.

## Test evidence

- 154 passed: `tests/pubpartner_core`, `tests/pubpartner_vessel`, Foresight front door/cohesive program, shared auth, Alex memory reach/backup, and new continuity/privacy tests. No failures in this selection.
- Dedicated restart test persists a private Alex turn, reconstructs bridge+spine+vessel, and verifies both old user text and old Alex response reach the next FCP1 prompt.
- Dedicated tests verify owner separation, shared-room isolation, fake-provider exclusion, persistent owner voice edits, open-ended memory recall, and local model context sizing.
- JavaScript syntax and modified Python compilation passed. Source archive checksum verification is recorded by the package manifest.

**Limits:** These tests use a labeled provider emulator, not a real LLM. No live Ollama/server model or external API credentials were available; the quality of a real Alex conversation is not established. Google Drive backup was not retested against the real service. Private long-term recall is keyword-based, except for explicit open-ended recall requests. The entire application and physical/studio subsystems are not commissioned by this pass. The full repository-wide test suite was not run here; the 154-pass selection is not a claim of full-suite certification.

## Use

Extract this ZIP as the next single authoritative PubCast source directory. On Windows use `OPEN_REACH_WINDOWS.bat`; on Linux/macOS use the existing `run_reach.py` launch procedure. Open Foresight and enter PubPartner → Alex. PubPartner checks Ollama on the host's configured Ollama URL; if an installed model is found, it can select it. Other model providers require their existing credentials. No model means no speech, *not* a fake response. Memories and personality files persist under the main program's configured data directory. Preserve the original `data/` directory when updating an existing installation: do not replace it with the ZIP's empty directory skeleton.

## Historical build manifests

Previous `AUDITED_FILE_MANIFEST_SHA256.json` and `FORESIGHT_FILE_MANIFEST_SHA256.json` belong to older releases. The current archive's file hashes are in `ALEX_MEMORY_PERSONALITY_SHA256_MANIFEST.json`. Do not treat historical manifests as hashes of this new build.
