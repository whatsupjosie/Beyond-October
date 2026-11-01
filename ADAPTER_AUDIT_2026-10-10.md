# Adapter audit findings and disposition

Fixed in this revision:
- Local FCP1 translation: preserve source/history exactly, retain relevant persona,
  guidance, memory provenance and references; avoid duplicated custody instructions.
- Measure actual rendered token count before local generation; reject overflow.
- Reject truncated, malformed, blocked, timed-out and incomplete model replies.
- Preserve exact user/assistant history on all three hosted adapters.
- Use OpenAI Responses; isolate instance credentials; remove Google key from URL.
- Fail unavailable selected credentials instead of using an unrelated host key.
- Strip client-supplied server-secret selectors from public provider routes.
- Verify local health with launcher credentials and validate runtime identity.
- Supervise both child processes; handle termination; check model checksum.
- Serialize same-owner/session turns and discard stale browser responses.
- Prevent duplicate sends; recover drafts; reset history on identity/session change.
- Preserve answer meaning during neutralization instead of stripping subjects/hedges.
- Give manuscript generation an explicit new-prose task; reject overlong instructions.
- Create and validate dependencies before launch; add hosted-only launchers.
- Keep mock/offline fallback disabled by default in the live UI.

Primary changed files include modules/bot_llm_adapter.py,
openai_responses_provider.py, openai_compatible_provider.py, smollm_prompt.py,
local_model_config.py, pubpartner_provider.py, pubpartner_routes.py,
turn_serialization.py, pubpartner_core.py, pubpartner_knowledge.py,
provider_neutralizer.py, pubpartner_voice.py, manuscript_intelligence.py,
writers_room.py, static/pubpartner.js and .html, setup_smollm.py, run_smollm.py,
the startup wrappers, focused tests and the reproducible live-check tool.

Evidence: SMOLLM_VALIDATION.md and validation/. All files included in each
archive have a fresh SHA-256 manifest matching that archive's actual contents.
The code/runtime edition intentionally omits the GGUF. Historical manifests
from the base build remain historical, not authoritative for this revision.

Remaining: real authorized hosted replies; subscription OAuth integration and
eligibility; Windows/phone/browser commissioning; broad model-quality tests;
original four-round open issues. There is no claim that every legacy subsystem
has been audited or that the complete application is production-ready.
