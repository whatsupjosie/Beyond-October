# Blackbox five-round troubleshooting — session ending handoff

Later update: automatic canonical-room-chat replay is implemented and tested in
[Automatic Blackbox chat recovery](BLACKBOX_CHAT_REPLAY_2026-11-09.md).
The replay limitation below describes the state at this five-round checkpoint.

Work date: 2026-11-09. Branch: `gpt/live-studio-setup-2026-11-09`.
Scope: the background event witness, room chat, bot coordination and offline
verification. No audio UI or avatar-animation changes.

The owner's requested starting severity was interpreted as rigorous integration
review, escalating through injected failures, concurrency, recovery and
adversarial checks. No existing shared numbered severity scale was assumed.

## Executed rounds

| Round | Reproduction and defect | Correction | Executed result |
| --- | --- | --- | --- |
| 1 — boundaries and event integrity | Five failure cases: extra/duplicate wire fields passed parsing; unsafe session IDs escaped the ledger directory. | Reject unknown/duplicate BBX1 fields and unsafe session filename components. No existing files are renamed or rewritten. | Before: 5 failed. After: 15 selected tests passed, 4.86 s. |
| 2 — injected event failure | A successful heartbeat cleared the apparent effect of a rejected event; malformed event data escaped the runtime safety boundary. | Retain degraded coverage and failure-attempt count separately from connection health. On the next successful write, append an explicit coverage-gap receipt. Convert invalid data inside the guarded path. | Before: 2 failed. After: 20 selected tests passed, 13.02 s. |
| 3 — storage and concurrent access | Truncation permitted appending onto damaged storage; a removed ledger verified as an empty success; ledger permissions depended on the process umask. | Check expected file size/identity before appending, refuse missing live ledgers, detect lost committed records, synchronize reads, and create/write ledgers with POSIX mode 0600. Fsync the new file's directory entry on POSIX. | Before: 3 failed. After: 38 selected tests passed, 4.64 s, including the concurrent writer checks. |
| 4 — restart and coverage audit | Offline verification could report complete coverage while saved chat had no witness; persisted gap notices were ignored. | Compare canonical room logs against chat receipts using room, message ID, actor, exact-text hash and timestamp. Retain known failure counts from gap records across ledger sessions. Empty ledgers cannot establish successful coverage. | Before: 2 failed. After: 25 selected tests passed, 6.58 s, including real loopback HTTP/WebSocket capture/restart tests. |
| 5 — adversarial cross-component checks | Entire deleted room archives escaped the comparison; malformed capture metadata could crash the inspector; PubPartner dispatch exceptions/cancellation lacked terminal events; explicit reopen did not recover a latched writer or verify corrupted source. | Compare receipts back to canonical archives too; reject malformed receipt data and report bad sidecars; journal dispatch failure/interruption with the original turn ID; verify and reconstruct recorder state on explicit reopen. Disabled witnesses stay inactive. | Four initial product failures plus two later reopen failures were reproduced and corrected. Concurrent shutdown also exposed a test assumption about performance records; see below. Combined regression and final recovery results below. |

The stages are distinct passes; their test counts overlap and must not be added
as if they were independent test inventories.

## Final evidence

- Combined regression selection after the reopen correction: **112 passed**,
  47.19 seconds, 17 existing dependency deprecation warnings.
- After handling the disabled-witness reopen case, the focused selection:
  **30 passed**, 15.46 seconds, 5 existing dependency deprecation warnings.
  This overlaps the 112-test selection and includes the added disabled case.
- `tools/blackbox_smoke.py`: passed.
- `tools/blackbox_hardening_check.py`: passed.
- `git diff --check`: passed before commit.

The combined selection included the new five-round cases and existing background
event tests, full-host restart tests, room chat commit/identity boundaries,
Blackbox language/storage/media hardening, real loopback HTTP/WebSocket capture,
bot turn requests, camera broadcast ordering, Alex/Jeremy and Pub Manager
authority contracts, PubPartner live-loop contracts, capture disconnect, and
the host's shared-bridge lifecycle test.

The abrupt-exit test runs a real child process, commits forty numbered events,
then calls `os._exit(17)` without witness close or Python shutdown hooks. A new
recorder verifies all forty exact events and the chain, with no false clean-stop
marker. This is process-termination evidence, not a hardware power-loss test.

Concurrency tests include an eight-worker event stream racing shutdown. The
final record must be the unique shutdown marker, with no events afterward and a
valid chain. Existing concurrent-writer tests also remain passing.

A test defect was corrected separately from product defects: performance-pressure
records legitimately do not contain the adapter's `event_type` payload field.
Event filters now use `.get('event_type')`; all exact text, count, correlation,
chain and shutdown assertions remain. This prevents slow-storage warning records
from causing spurious KeyErrors in the tests.

## Resulting behavior

Connection health and coverage are separate. `connection=running` proves the
current heartbeat was durably written. `coverage=degraded` reports failed event
recording attempts in this process, even after later successful writes.
`coverage_scope=current_process` prevents interpreting that field as an audit
of all historical sessions. The offline inspector reads historical gap receipts.

A failed fsync may leave a full valid record already written, so a failure count
means failed/uncertain acknowledgement attempts, not necessarily that every
counted event is absent. There is no automatic blind retry that might duplicate
already committed events. An explicit verified reopen reloads sequence/hash from
actual bytes before recording a restart marker.

Offline chat results count missing receipts, changed contents/identity/timestamp,
duplicates, unarchived receipts, legacy unidentifiable entries and read errors.
Reports use metadata/counts and text hashes, not raw chat text. A valid hash chain
alone is no longer enough for a complete-coverage result. Run the inspector only
against a stopped host or stable snapshot for reliable comparison.

No existing runtime ledgers, room archives, media originals or owner credentials
were repaired, migrated or published. Tests use temporary isolated data. No new
player-facing review/delete/edit route was added. No merge or deployment.

## Remaining limits

- Automatic outbox replay/reconciliation of unwitnessed chat is still absent.
  This pass detects gaps; it does not manufacture missing history.
- A process that dies before a failed-attempt notice can itself be written may
  leave no gap receipt. The room archive comparison detects retained unwitnessed
  chat, but there is no separate durable source for every possible system event.
- Deleting both a canonical chat archive and all its witness records cannot be
  detected without an independent trusted inventory or external anchor. Hashes
  do not provide authenticity against rewriting the entire evidence set.
- Existing privacy filters remain. The audit covers named integration paths,
  not all subsystems or inaccessible model reasoning. High-rate motion frames
  remain excluded from the background event journal.
- Locks remain in-process. Do not share a ledger file between independent writer
  processes. Size/inode guards detect accidental replacement or concurrent
  external changes; they are not a multi-process transaction protocol and do not
  detect every same-size external edit at append time. Full verification still
  checks the chain.
- POSIX permission tests ran on Linux. Windows ACL behavior, actual Android UI,
  physical microphone input and live external model availability were not tested
  here. Provider exceptions/cancellations use deterministic doubles; full-host
  turn logging uses the built-in mock provider.
- No complete repository suite, long-duration load benchmark, physical disk-full
  test or hardware power-loss test was run. Durable synchronous writes can delay
  event delivery on slow storage. Continuous studio audio capture is unchanged.
