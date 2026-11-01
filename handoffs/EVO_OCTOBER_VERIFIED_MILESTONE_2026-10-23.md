# October EVO integration — verified compatibility milestone

Date: 2026-10-23. Owner: Codex / Josie Curtsey Cobbley.

## Status

The requested narrow EVO semantic integration is implemented and applied to the existing local October consolidation tree. The two recovered E-Pete protections are also implemented. The full focused suite passes after integration: **81 passed, 1 dependency deprecation warning**. This is not a certification of the entire PubCast application or hardware stack.

## Changes

- Each EVO tick and direct signal injection now translate VDI observations through `VDISemanticAdapter`, role-aware arbitration and `SemanticRuntime` into one immutable performance snapshot. Changed snapshots emit typed `semantic.updated` events after commit; observers receive committed revisions.
- `EVOTick.semantic_state`, `get_semantic_state()` and additive state-summary fields expose that snapshot. The optional tick field is appended so existing positional constructor arguments retain their meanings.
- `semantic_enabled=False` bypasses semantic proposal/commit/dispatch and retains the old state-summary/shoulder-context shape. The original VDIEngine, ProsodyEngine and Switchblade calculations remain byte-identical.
- The local EVO performance store does not replace System Alex's personal emotional adjudication, durable memory, Blackbox, or the application's existing event infrastructure.
- The recovered frozen safety-state container now copies and protects its flags mapping. Its explicit snapshot export returns detached JSON-ready dictionaries.
- E-Pete repeated starts retain one live worker. Stop/restart works without an orphaned old worker.
- E-Pete inference calls have configurable positive finite deadlines for Studio and Architect. Both default to 180 seconds to accommodate slow local cold starts; they can be set through either `EPete(...)` or `EVOOrchestrator(...)` keyword arguments. Models and routing defaults are retained. Timeout failures flow through the existing inference-result error path; cooperative cancellation releases the inference slot.
- The donor's prosody adapter and tests are preserved, with appropriate approximate float assertions. **The adapter is not invoked by the orchestrator in this compatibility slice.** Existing voice behavior remains unchanged; semantic prosody conditioning/output-instruction migration is separate work.

## Source and preservation

October base for publication: `Backup-Consolidation` at `33b45d812ab501fa2a4eadb330486075067ba6be`. Relevant local source was matched against that published base before application. Donor semantic primitives: Wednesday branch `evo-semantic-runtime`, commit `a4b193b24c760520cfcf9eb067c68dea100b24d3`. E-Pete protection ideas verified against Friday Lunch's `pubcast_evo_FINAL.zip`; only the narrow protections were ported. Old recording monkey-patches, hardcoded model names and alternative entry points were not installed.

Existing modified files: `modules/evo/__init__.py`, `modules/evo/evo_integration.py`, `modules/evo/epete.py`. Eight semantic source modules and eight test modules were added. Unrelated October source, UI work, data and credentials were not included in the change.

## Verification

Baseline: the original EVO protocol suite passed 33 tests before changes. The isolated integrated suite passed 81 tests. After source-hash guards and application to the original local October tree, the same suite passed 81 tests with the normal repository conftest loaded.

```powershell
python -m pytest -q tests/test_evo_protocol.py tests/test_round9_evo_irm_bridge_contract.py tests/test_evo_event_bus.py tests/test_evo_orchestrator_semantic_wiring.py tests/test_evo_semantic_runtime.py tests/test_evo_semantic_runtime_coordinator.py tests/test_prosody_semantic_adapter.py tests/test_vdi_semantic_adapter.py tests/test_evo_october_integration.py tests/test_epete_lifecycle_deadlines.py
```

Executed with an isolated Python 3.12 environment: pytest 9.1.1, pytest-asyncio 1.4.0, numpy 2.5.4, psutil 7.2.2, FastAPI 0.161.1, Starlette 1.9.0, httpx 0.28.1 and pydantic 2.14.1. October's dependency declarations were not changed. The integrated run produced one Starlette/httpx deprecation warning from the existing conftest import; no tests failed or skipped.

The tests cover real orchestrator construction and async ticks, adapter/store/event ordering, changed revisions, preserved voice/render output values, injected signals, state isolation, observer failures, snapshot immutability, compatibility bypass, old EVOTick positional arguments, lifecycle cleanup, existing IRM/Switchblade contracts, E-Pete repeated start/restart, generate/chat deadlines for both model lanes, cancellation, timeout failure results and successful inference after a timeout. Camera-analysis outputs and engine/camera targets are simulated where needed. No model API, microphone, camera or cloud inference was called.

## Limits

- Full application HTTP/UI startup and live traffic were not exercised in this milestone; the orchestrator is tested directly within October's source tree.
- Physical camera analysis, audio/TTS output, actual local model performance, GPU/Rust rendering, Windows and real device behavior remain untested.
- Inference deadlines bound cooperative async backends. A backend that blocks the event loop or suppresses cancellation can require process-level supervision; this change does not add that infrastructure.
- The semantic store uses the donor's optimistic revision guard: concurrent stale writes raise rather than silently overwriting state. A shared multi-writer retry strategy is not added here.
- Snapshot storage is in-process. This slice does not claim durable semantic persistence or automatically wire external ChatGPT conversation capture.

## Rollback

For behavioral bypass of the semantic path, construct `EVOOrchestrator(semantic_enabled=False)`. E-Pete protections remain enabled.

For full source rollback, revert the dedicated milestone commit on the published feature branch. Original `main` and `Backup-Consolidation` branch heads are not moved by creating the feature checkpoint. In the local consolidation workspace, restore only the three changed original files from the preserved baseline and remove only the sixteen newly added source/test files if their hashes still match this milestone. Never reset the whole synthetic working tree or discard unrelated integration work.

## Task continuity / next work

- EVO-01 semantic orchestrator compatibility slice: COMPLETE for the tested scope above.
- EVO-02 E-Pete repeated-start/deadline protections: COMPLETE for the tested scope above.
- PROSODY-01 semantic snapshot conditioning/output-instruction migration: QUEUED.
- COMPANION-01 Friday emotional/companion recovery: QUEUED; recover located helpers, resolve missing observation/contradiction implementations, repair imports, then adapt to October's current conversation and System Alex boundaries.
- Tuesday shared-performance-manager repair and other audit candidates remain recorded in the weekday recovery audit.

New ideas and investigations add to the task queue unless the user explicitly switches priority. A finished audit never silently replaces an unfinished implementation task.
