# EVO semantic prosody integration — October 25, 2026

## Completed slice

EVOOrchestrator now executes VDI calculation, adapter proposals, arbitration,
semantic-store commit, typed semantic.updated event, and read-only prosody
conditioning in its real async tick. Prosody consumes the exact immutable
snapshot returned by that tick, including when a subscriber commits a later
revision before dispatch finishes. Provider-neutral SynthesisParams records the
consumed semantic_revision; provider conversion schemas remain unchanged.

VDIEngine stays the compatibility calculation engine. Switchblade still consumes
the original VDIReport. Character constraints are applied after conditioning.
The default room weight is 0.25, preserving 0.75 performer contribution for the
three conditioned fields (valence, arousal, tension). Other performer fields are
retained. The adapter returns a detached EmotionalState and does not write to
the semantic store. This is EVO performance state, not a replacement for System
Alex or PubPartner personality, relationship policy, or persistent memory.

This supersedes the pending semantic-prosody step in the October 23 milestone.
The recovered milestone foundation and its tests are included because current
October main did not contain them. The earlier E-Pete lifecycle/deadline fixes
remain in place: idempotent start and configurable 180-second default backend
deadlines. No Friday companion or Horizon docking changes are in this update.

## Reversibility and compatibility

- semantic_prosody_enabled=False retains semantic commits/events while restoring
  the original performer-to-prosody input. It can be changed between ticks.
- semantic_enabled=False bypasses semantic proposal/commit and conditioning.
- semantic_room_weight=0 preserves valid performer delivery values while still
  recording the snapshot revision consumed. Invalid weights are rejected.
- VDIEngine, Switchblade, facial analysis, camera manager, distributed engine,
  Pete character and voice profile sources are unchanged from parent main.
- ProsodyEngine calculation and provider conversion methods are unchanged; only
  optional semantic_revision metadata was appended to SynthesisParams.

## Verification actually executed

103 tests passed, zero failures, zero skips, in an isolated 34-file EVO candidate
on Python 3.12.14, pytest 9.1.1, pytest-asyncio 1.4.1, numpy 2.5.4, psutil 7.2.2.
The candidate contains all 19 EVO Python files, modules/__init__.py, irm.py,
circuit_breaker.py, bridge_raw.py, and the 11 selected test files. All existing
dependency files match parent GitHub main b44db358455d1d5e2467e4802afd91b3f3051dba
by Git blob hash. This excludes all companion work and application-wide archive
changes. The original 94-test group also passed in the larger working tree.

From repository root, with the dependencies above installed:

```bash
python -m pytest --noconftest -q -ra --asyncio-mode=auto \
  tests/test_evo_*.py tests/test_epete_lifecycle_deadlines.py \
  tests/test_prosody_semantic_adapter.py tests/test_vdi_semantic_adapter.py \
  tests/test_round9_evo_irm_bridge_contract.py
```

The --noconftest option deliberately excludes unrelated full-PubCast host
fixtures. These are EVO-focused tests, not a full application acceptance run.
Actual output and JUnit results are in handoffs/evo-verification-2026-10-25/.

Covered paths include real async ticks, inject_signals, commit-before-notify,
revision reuse for no-op ticks, arbitration and store revision conflicts, typed
bus duplicate/recursion/error isolation, immutable safety flags, observer writes
during dispatch, per-instance state, actual changed synthesis parameters,
unchanged VDI and render priority outputs, legacy bypass, runtime disable,
character ceilings, provider schema compatibility, E-Pete worker shutdown and
backend timeout behavior, plus the existing real localhost UDP heartbeat and
typed command exchange between two distributed engine nodes.

## Review boundaries and remaining verification

No live camera or DeepFace/MediaPipe inference was exercised: frame-to-emotion
inputs are synthetic at that boundary. No voice provider was called and no
audio was synthesized or listened to. GPU/Rust rendering, physical device or
phone deployment, remote networking and full PubCast boot were not tested.
The default room weight is a configurable engineering choice, not perceptually
calibrated voice quality. Event payload containers are now recursively immutable structured data; live
mutable runtime objects are rejected. Roles remain a trusted in-process caller
contract; this change does not claim authentication or hostile-plugin isolation.

The completed scope is the orchestrator semantic-runtime and semantic-prosody
slice. Wider host activation, replacement of the legacy VDI algorithm, and
companionship/docking upgrades are separate work. No broad rewrite is included.

## Additional review requested by the user

Three defects were reproduced with six failing regression tests before fixes:

1. An explicitly empty arbitration permission dictionary accidentally restored
   default authority through a truthiness fallback. The arbitrator now defaults
   only on None and owns a detached copy of the permission policy.
2. Arbitration compared only exact paths, allowing a lower ranked container
   replacement to erase an accepted higher ranked leaf, or the reverse. Parent
   and child paths now conflict; the first ranked accepted proposal owns that
   subtree for the batch. Disjoint sibling fields still arbitrate independently.
3. A frozen event dataclass still held an aliased mutable payload dictionary.
   A subscriber could change the revision observed by later subscribers. Event
   payload mappings are now owned read-only mappings, arrays are immutable
   tuples, and live arbitrary runtime objects are rejected at construction.
   Existing structured-data event consumers retain mapping/index access.

The regressions now pass. A separate real two-thread test confirms that two
competing writers produce exactly one committed revision/event and one explicit
revision conflict; no silently lost update is accepted. The entire isolated
103-test suite also passed with PYTHONASYNCIODEBUG=1 and ResourceWarning promoted
to an error. This supplements the normal run; these are the same 103 cases,
not 206 distinct tests. Source parsing and git diff --check also passed.
The before-fix failure output is retained as audit-red-output.txt; current green
results are pytest-output.txt and debug-pytest-output.txt.
