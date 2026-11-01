# Five-round PubCast review — October 25, 2026

The review started from the exact full-build ZIP delivered to the user, not a
different checkout. Confirmed defects were corrected, existing integration
candidates were kept separate, and the final full suite passed under strict
resource/runtime-warning checks. Earlier failing logs are retained as evidence;
they do not describe the final state.

## Final verified result

- **1,409 passed, 6 skipped, zero failures/errors**, full discovered Python suite.
- Asyncio debug enabled; ResourceWarning, RuntimeWarning and pytest unraisable
  exception warnings promoted to errors.
- **389 passed**, separate EVO/companion focused selection, including explicit
  legacy horizon_ref tests that normal test discovery does not collect. These
  overlap the full suite; do not add the counts together.
- Portable PubPartner **0.3.0** wheel smoke passed in isolated Python with zero
  PubCast imports; distribution metadata now matches the public API version.
- pip check passed in a fresh environment installed from the declared production
  dependency ranges, including FastAPI 0.115.14, Starlette 0.41.3 and
  cryptography 48.0.1. Earlier focused checks used newer versions outside these
  declared ranges; the final result corrects that verification gap.
- All **1,131 files in the pinned repository baseline are now present** in the
  full working package. The original package omitted 51 baseline records.

## Round 1 — artifact integrity, completeness and dependencies

The original included files matched their recorded checksums and all 653 shipped
Python files parsed. That was insufficient as a completeness check: a comparison
against the entire repository inventory found 51 omissions, including avatar
metadata, seed records, a vessel and a bridge bundle, plus storage scaffolding.
All were restored by exact Git blob hash. Existing cartridge files were not
replaced or rewritten. Required runtime folders now survive packaging.

A fresh environment was built from production requirements. Portable test
dependencies were added to requirements-dev.txt so the focused verification
script does not depend on undocumented manual installs. Playwright remains
optional browser verification, not a runtime requirement.

## Round 2 — full-host startup, ownership and actual interfaces

Two new tests first failed: the host reported an EVO object but never started its
worker, and /api/evo/status asked for a method the orchestrator did not expose.
The host now starts/stops its owned E-Pete worker and reports real semantic state,
running/worker flags and whether rendering/camera managers are actually attached.
No fictitious rendering or live sensing is reported.

The host InferenceManager exposes generate_text(), whereas E-Pete expected
generate()/chat(). A narrow adapter now translates E-Pete's existing routing
aliases into the host's Studio/Architect API, preserves context, and rejects
reported errors, unexpected fallback and empty results instead of claiming the
assigned model succeeded. Configured physical model selection remains owned by
InferenceManager; the adapter does not replace the user's model configuration.

The assembled archive's host wiring was reconciled with the published entry
point using a three-way merge. This restores already-present Counter, workspace,
host-tooling and communication routes, binds the actual speech engines, and
retains authenticated private-chat, provider and BlackBox ownership. This was not
a wholesale overwrite with an arbitrary straggler version.

Nested TestClients borrow a live app; they must not close another loop's tasks or
database handles. The assembled host's ownership guard is retained alongside the
new EVO startup/re-arm path. True startup/shutdown tests now run in isolated
processes with their original assertions, rather than accidentally testing a
borrowed app while the session fixture still owns it. Nested EVO borrowing and
sequential worker restart have explicit regression coverage.

## Round 3 — EVO runtime and typed callback contracts

The 389-case selection passed in the declared dependency ranges. Two new callback
tests reproduced a sync EventBus accepting async callbacks, counting them as
delivered, and never executing them. Async subscribers are now rejected;
wrapped awaitables produce an observable isolated dispatch failure, with owned
coroutines closed rather than leaked. Other subscribers continue to receive the
committed event. VDI calculation, immutable snapshot provenance, character voice
constraints and legacy bypass remain covered.

## Round 4 — data, transactions and privacy/error boundaries

A new test reproduced partial data surviving when an inner sync write failed and
its caller caught the exception inside an outer transaction. Nested transactions
now use SQLite savepoints. Failed nested writes roll back their own data and
clock while a later valid write can still commit. Existing batch rollback,
restart/retry, deletion, conflict and relay cases remain green.

An empty owner's conversation search could avoid executing SQLite FTS parsing and
incorrectly accept a malformed query. FTS syntax is now validated independently
of ownership joins, returning a client error consistently without exposing other
owners' search results. Existing ownership tests pass.

One old nudge privacy regression still mocked the pre-invitation scheduling path.
It was updated to test the current voluntary request_turn boundary: declining
causes no speech, private directions never enter public history, internal nudges
do not recurse, and ordinary public chat still schedules a reply. Production bot
behavior was not weakened to satisfy the obsolete test.

## Round 5 — broad regression, resources, distribution and packaging

The first broad pass stopped at 12 failures after 829 passes; missing host wiring
and package records were repaired. A later pass found four outdated test
assumptions: the Counter intentionally stays blank without saved state, and nested
clients no longer own startup/shutdown. Assertions were brought into line with
those existing intended behaviors, with isolated processes preserving genuine
ownership/lifecycle checks.

One browser test unconditionally imported optional Playwright and blocked suite
collection. It now explicitly skips when unavailable, matching the other browser
tests; no browser behavior was claimed verified.

The ordinary suite then passed 1,407 tests. The strict resource pass caught two
unclosed FFmpeg output pipes after a real generated-file camera capture. Camera
cleanup now closes owned pipes even when the process already exited, and reaps a
forced kill before releasing its streams. Two new regressions first failed and
then passed. The final strict suite passed **1,409 tests**.

The old wheel advertised version 0.1.0 while its public API reported 0.2.0. A new
smoke assertion reproduced that mismatch. Both now report 0.3.0, preventing the
updated distribution from masquerading as the older package version.

## Skips, warnings and remaining limits

The six skips are four browser verification paths (Playwright/browser tools,
including a widget check requiring BeautifulSoup) and two intentionally disabled
Alex Little One research paths. None is silently reported as a pass.

The final strict run recorded **134 DeprecationWarning instances**. They are
legacy API/time handling maintenance, not suppressed resource or coroutine
failures. They remain technical debt; no broad untested timezone/API rewrite was
introduced just to silence them. The complete classified warning record is
included with the evidence.

Real FFmpeg-generated file frames, real SQLite stores, local HTTP app routes and
local UDP contracts were exercised. This does not validate physical cameras,
microphones, live-model emotional quality, GPU rendering, Windows/phone deployment
or browser UI. Render/camera attachment to the EVO host remains explicitly
unconfigured. Automatic remote Horizon pairing/transport/discovery remains a
separate unimplemented feature, not merely an unrun test. The EQ revamp plan and
other unrelated integration candidates remain pending.

## Reproduce

With requirements.txt installed plus the non-browser test dependencies from
requirements-dev.txt:

```bash
PYTHONASYNCIODEBUG=1 python scripts/verify_companion_recovery.py
PUBCAST_WARNING_AUDIT=warning-audit.json PYTHONASYNCIODEBUG=1 python \
  -W error::ResourceWarning -W error::RuntimeWarning -m pytest \
  -p scripts.pytest_warning_audit -W default::DeprecationWarning \
  -W default::PendingDeprecationWarning \
  -W error::pytest.PytestUnraisableExceptionWarning -q
```

Actual commands/results, JUnit, before-fix failures, supported environment and
warning inventory are in handoffs/five-round-review-2026-10-25/.

The readable JUnit retains every testcase, outcome and timing. One generated
identifier embedded a 24 MiB rejection-test payload, making the report 25 MiB.
That identifier is shortened in the readable copy and traced by SHA256; the
byte-exact original report is preserved as round5-strict-final-junit.raw.xml.gz.
The test now has explicit bounded case IDs, retaining the same oversized input
and rejection assertions. No test outcome was edited.
