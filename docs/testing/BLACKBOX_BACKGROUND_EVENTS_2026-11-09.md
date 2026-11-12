# Blackbox background events — session ending handoff

Later update: the automatic canonical-room-chat replay gap described below is
addressed in [Automatic Blackbox chat recovery](BLACKBOX_CHAT_REPLAY_2026-11-09.md).
This document preserves the earlier checkpoint and its executed evidence.

Date: 2026-11-09. Branch: `gpt/live-studio-setup-2026-11-09`.
Priority: accurate chat, bot coordination and system event history; studio audio
capture remains separate work.

## Changes and rationale

Four new failure-focused tests reproduced missing system emissions, missing
bridge receipts, missing initial bot-request state, and loss of nested details.
The first fixes then exposed a wire-format defect: payload values allowed literal
commas even though commas delimit fields. Exact chat text and serialized JSON
could therefore decode incorrectly despite a valid ledger hash.

New payload writes escape commas. Existing decoders already understand escaped
values, and existing ledger bytes/hashes are not changed. The adapter retains
its scalar projection and adds canonical `data_json`, preserving nested values,
types, nulls and original data fields. Envelope event identity and source name
cannot be replaced by similarly named fields in event data.

Selected existing integration points rather than adding a second event bus or
scraping application console logs: those alternatives would miss private
coordination context or multiply records per recipient. This work captures
published messages/events, not inaccessible model reasoning.

- Hub room chat retains its existing exact text, authenticated sender,
  message ID, room and timestamp witness path. Bot speech uses that same path.
- Hub system announcements are witnessed once per broadcast invocation before
  delivery, including with no listeners. Full nested announcement details are
  retained. This records emission, not proof of receipt by every client.
- Alex/Jeremy bridge and Pub Manager authority use an installation-scoped dual
  audit callback in the real host. The existing audit file remains; the same
  already-filtered event enters the main hash-chained ledger as `internal.audit`.
  A failure in either write propagates to the existing fail-closed authority
  handling. The callback rejects a different runtime's data directory.
- Requested bot turns record the initial request and exact invitation/direction,
  followed by existing ordered request states. Automatic and requested reply
  generation record starts, skips, failures, cancellations and completions,
  using a generation ID and trigger/request IDs. Successful generation links
  to the actual persisted chat message; failed generation invents no speech.
- PubPartner records turn input plus Jeremy's generated coordination note before
  provider dispatch. The completion record includes the turn ID, recipient friend,
  actual reply, provider outcome/error and receipt ID. These events now have
  appropriate chat/action mappings instead of unknown-error classifications.

## Executed evidence

Final combined selection: **87 passed**, 27.31 seconds, 13 existing dependency
deprecation warnings. Included background event tests, recorder corruption and
recovery, existing room-chat commit/identity boundaries, requested bot turns,
camera ordering, bridge/authority contracts, PubPartner live-loop contracts,
and real loopback HTTP/WebSocket capture/restart/preservation.

The new full-host test launches the actual `main.app` lifespan in an isolated
subprocess. It sends chat and a production-state announcement through actual
HTTP handlers, runs PubPartner through the built-in deterministic mock provider,
and checks exact text, nested coordinator notes, audit records and ledger chains.
A second app process reopens the same temporary data and verifies the records
and chat survived. This is a real app/process restart test using TestClient;
it is not an Android, browser, or live external model test.

Generated bot replies also exercise real Hub storage and real Blackbox files;
only provider output is doubled. A failed-provider test verifies correlated
start/failure records and the absence of fabricated chat. Owner runtime data
and credentials are untouched. No new player-facing Blackbox browsing route.

## Limits and next checks

- This verifies the named paths, not every subsystem's events. Other callers of
  the legacy dressing-room security logger still write their original log only;
  direct private character chat retains its separate existing witness path.
- High-rate `mocap_frame` and `choreo_frame` system broadcasts are excluded from
  this event journal. Their start/control/stop announcements remain eligible.
  This pass does not establish complete motion-frame recording elsewhere.
- Historical unescaped-comma payloads remain ambiguous when decoded. This fix
  does not retroactively reconstruct them; canonical room logs may supply exact
  originals. Preserve old evidence before undertaking reconciliation.
- Canonical room chat commits before its independent Blackbox witness. A witness
  failure returns the existing warning; automatic outbox replay/reconciliation
  is still absent. System/bot witness failures log explicit errors and do not
  stop ordinary production. There is no claim of gap-free recording through
  arbitrary storage failures or of externally anchored authenticity.
- The two internal audit writes are not one atomic transaction. A partial write
  remains evidence and blocks success rather than being deleted or retried
  silently. Authority correlation IDs distinguish decisions from observations.
- Existing privacy filters remain in place. Credentials/private memory are not
  newly dumped into the shared bridge log. Offline Blackbox records remain
  sensitive runtime data and must not be committed or published.
- No long-duration event-volume/latency benchmark or disk-full hardware test was
  performed. Synchronous durable emission preserves ordering but can delay work
  on slow storage. Browser audio always-on coverage is unchanged by this pass.

Committed on the work branch only; no merge or deployment.
