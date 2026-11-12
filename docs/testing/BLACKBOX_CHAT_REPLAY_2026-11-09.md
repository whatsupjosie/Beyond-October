# Automatic Blackbox chat recovery — session ending handoff

Work date: 2026-11-09. Branch: `gpt/live-studio-setup-2026-11-09`.

## Result

Closed the previously documented automatic replay gap for canonical room chat,
including bot speech stored through Hub. The actual host starts reconciliation
on startup and retries every two seconds. App-singleton re-entry re-arms the
worker; shutdown waits for delivery work to finish before closing the witness.

Recovery preserves exact text, sender, room, original timestamp and message ID.
It appends missing Blackbox receipts only. It does not rebroadcast chat, append
another room message, rerun AI callbacks, or rewrite historical ledger records.
Recovered receipts have `delivery_mode=replay`; BBX record time remains the actual
delivery time and payload `t` remains the original message time.

## Implementation and chosen approach

Considered three approaches: blind archive replay (duplicates already recorded
messages), an outbox alone (misses the crash window between canonical append and
queue insertion), and a durable delivery queue plus source/archive and receipt
reconciliation. Implemented the third, using the existing private FULL-synchronous
SQLite database and a separate `blackbox_chat_outbox` table.

The room JSONL remains the source of truth. The queue contains an immutable
canonical snapshot and fingerprint for delivery, not a second chat-send system.
Keyed sends retain their existing cross-process idempotency. Unkeyed sends still
create independent messages when invoked again; recovery deduplicates each saved
message by its server-issued message ID.

1. After room commit, Hub enqueues delivery and tries it on a worker thread.
2. Startup verifies existing journals and reconstructs acknowledged delivery
   identities, including receipts created before this queue existed.
3. Archive scanning discovers committed messages that never reached the queue.
   In-process file cursors then inspect appended bytes on later passes.
4. Before a BBX write, a committed SQLite reservation identifies its attempt and
   destination ledger. A second transaction serializes delivery. A competing
   worker that takes over verifies the prior attempt's ledger before retrying.
5. If the process dies after BBX append but before SQLite acknowledgement, the
   next worker finds and fsyncs the existing receipt and marks it delivered.
   It does not append another receipt. Conflicting identities block recovery.
6. A transient failed fsync can latch the writer. The recovery worker verifies
   and reloads intact ledger bytes before resuming. Torn/corrupt ledgers remain
   blocked and untouched; no automatic truncation or repair is attempted.

Delivery is bounded to 64 pending messages per recovery pass. Initial archive and
ledger verification is a streaming history scan, with an identity set retained
during bootstrap. Queue rows remain for deduplication; no automatic pruning was
added. Multiple cooperating workers coordinate through SQLite and write their
own independent BBX ledgers. Sharing one BBX file between independent writers
remains unsupported.

## Visible failure behavior

The existing authenticated health endpoint now includes `chat_replay` with state,
pending count, latest recovered-delivery count, archive errors and unidentified
legacy-entry count. Pending count is `null` when storage cannot establish it.
Coverage stays degraded for blocked/pending recovery or known failed recording
attempts; a working heartbeat alone cannot clear that indication.

Keyed duplicate sends now retry/reconcile their Blackbox receipt without repeating
broadcast or AI work. A failed witness does not turn an already saved chat into a
false send failure. Historical coverage-gap notices remain as evidence even after
chat delivery is recovered; recovery does not erase earlier uncertainty.

No new player-facing browse, decode, edit, or delete route was introduced.

## Executed evidence

- Four new replay cases failed before implementation.
- Combined regression: **139 passed**, 53.00 seconds, 17 existing dependency
  deprecation warnings.
- Final focused review after pending-health handling and the altered-archive
  case: **26 passed**, 17.94 seconds, 1 existing dependency warning. These overlap
  the combined selection and must not be summed as separate test inventories.
- Both `tools/blackbox_smoke.py` and `tools/blackbox_hardening_check.py` passed.
- `git diff --check` passed before commit.

New executed cases verify:

- Exact punctuation/Unicode and original message identity after replay; offline
  audit then reports no missing or duplicate chat receipts for that fixture.
- Saved chat discovered after restart without rebroadcast or AI callbacks.
- Keyed retry repairing a missing witness with one room message and one AI call.
- A committed BBX record with a lost acknowledgement producing only one receipt.
- Two real child processes recovering ten shared messages without duplicates.
- Abrupt `os._exit(23)` before append and after append/before acknowledgement,
  followed by recovery from another process.
- An injected BBX-only fsync failure, automatic writer recovery when storage
  returns, and no duplicate receipt.
- Periodic recovery without another user send.
- Actual `main.app` startup discovering older saved chat and re-entrant startup
  re-arming the worker, with one receipt across both lifespans.
- Delivery-cache table loss rebuilding from verified journal evidence.
- Damaged ledger and altered canonical archive blocking recovery without source
  modification.

Regression coverage also includes five-round hardening, room identity/commit and
socket boundaries, bot turns, camera ordering, bridge/authority contracts,
PubPartner live-loop contracts, capture disconnect, real loopback HTTP/WebSocket
audio capture/restart, and the host's shared-bridge lifecycle.

All runtime data in tests was isolated. Owner account/runtime data was untouched.
The deterministic bot/provider tests establish delivery behavior, not external
model availability. This pass is backend work; no Android or Chromium UI test
was run or claimed. The unrelated pre-existing renderer artifact was untouched.

## Remaining limits

- This closes recovery for retained canonical room chat with stable identities.
  It does not reconstruct ephemeral system events or bot coordination messages
  that were never saved to another durable source, nor does it add replay of
  private-character transcript databases or other separate stores.
- Legacy entries without stable message IDs remain explicitly unidentified;
  IDs are not fabricated. Malformed/conflicting archives, corrupt ledgers and
  missing previously acknowledged witness evidence block replay for investigation.
- The queue/archive handoff is reconciled, not an atomic transaction across two
  files. Recovery relies on at least the canonical archive or its durably queued
  snapshot surviving. Deletion/corruption of all independent evidence cannot be
  repaired automatically.
- Retrying delivery does not retry AI callbacks. That would require a separate
  contract to prevent repeated model work and duplicate bot speech.
- No physical disk-full, hardware power-loss, Windows ACL, large-history startup
  latency or sustained-load benchmark was performed. The queue can grow during
  an outage; retention/rotation requires separate capacity work.
- Hashes prove consistency with retained evidence, not authenticity against an
  attacker who can rewrite the complete archive, queue and ledger set.

Committed on the work branch only; no merge or deployment.
