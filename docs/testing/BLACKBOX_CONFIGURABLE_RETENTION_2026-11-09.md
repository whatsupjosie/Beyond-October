# Configurable Blackbox archive limits — session ending handoff

Date: 2026-11-09. Branch: `gpt/live-studio-setup-2026-11-09`.

## Implemented behavior

The event-archive allowance and retention duration are saved configuration,
not fixed product limits. Provisional defaults remain 5,000,000,000 bytes
(decimal 5 GB) and six calendar months. The authenticated installation owner
can change the allowance and choose a positive retention amount in days,
weeks, months or years. No assertion is made that these defaults suit a measured
production workload; `defaults_provisional=true` remains explicit.

The existing operator boundary exposes:

- `GET /api/operator/blackbox/archive-policy`
- `PATCH /api/operator/blackbox/archive-policy`

PATCH accepts `expected_revision` and at least one of `storage_limit_bytes`,
`retention_value` or `retention_unit`. Unknown fields, null changes, nonpositive
values, booleans masquerading as integers, unsupported units and calendar
overflow are rejected. Revision checks prevent one settings editor silently
overwriting another. Settings and their before/after audit history commit in
the same FULL-synchronous private SQLite database transaction.

Owner authentication is mandatory even when legacy development authentication
is relaxed. Other roles and spoofed `X-Client-Id` headers cannot change limits.
The policy is installation-wide, not a guest-controlled allowance.

Fixed policy invariants are reported but cannot be edited through this schema:
flagged records remain Never Delete; active journals and pending deliveries
remain protected; Wallet custody is unaffected. Changing a limit does not
authorize unflagging or deleting anything.

## Dates and capacity

Calendar-month/year expiry calculation clamps to the destination month's last
valid day. August 31 plus six months becomes February 28 when appropriate;
February 29 plus one year becomes February 28. Day/week durations are distinct.
Calculations normalize timezone-aware creation dates to UTC and never replace
the original timestamp. This helper does not authenticate timestamps or enable
deletion; signed archive dates remain separate integration work.

The response reports actual host-volume free and total bytes, whether the
configured allowance exceeds current free space, and `preallocated=false`.
This is the host data directory's volume, not the remote phone/browser's disk.
Increasing an allowance changes a ceiling; it does not allocate or guarantee
physical storage. It may exceed today's free space, but that condition is
explicitly reported. A smaller allowance can also be saved without triggering
data deletion.

Archive-specific usage is deliberately `null` because the compressed archive
catalog is not yet active. Counting all live journals and WAV capture as if
they were completed event archives would give misleading usage figures.

## Audit delivery and recovery

Each accepted change has a stable `archive-policy:<revision>` identity and
durable actor, timestamp and before/after settings. Blackbox records the change
after settings commit. The existing recovery worker retries pending audit
observations without reapplying the configuration mutation.

Audit delivery is at least once: a crash between BBX append and SQLite
acknowledgement can repeat an observation with the same change ID. It cannot
repeat the settings change or advance its revision. Consumers should correlate
by change ID. This is distinct from the existing exactly-deduplicated canonical
chat delivery path.

If post-commit audit storage or capacity refresh fails, the response still
acknowledges saved settings and includes a warning/unknown delivery count or
capacity values. It does not falsely report that a committed change failed.

## Executed evidence

- Initial policy selection: 22 passed, 4.94 seconds.
- Broader regression after audit failure handling and real-host restart test:
  **98 passed**, 34.27 seconds, five existing dependency deprecation warnings.
- Final focused policy selection: **26 passed**, 11.69 seconds, one existing
  dependency deprecation warning. Includes disk-space warning and post-commit
  capacity-failure cases; this selection overlaps the 98-test regression.

Coverage includes authenticated owner-only HTTP handlers, hostile/invalid input,
persistence into a new witness and a new actual `main.app` process, concurrent
revision conflicts, calendar boundaries, lowering limits while a Never Delete
fixture remains byte-identical, audit retry, post-commit failure reporting,
free-space visibility, and the prior Blackbox/replay/hardening suites.
Tests used isolated data and did not change owner settings or credentials.

## Still pending

The owner settings screen is not wired. The operator API/storage works; no
player-menu Blackbox review or administrative surface was added.

Automatic cleanup is explicitly `false`. Archive-aware readers, safe compression,
archive catalog/usage accounting, flagged-date custody, expiry receipts and
replay integration must be completed before any expiration or capacity pruning
can be enabled. No archive files or user material were deleted, and no Wallet
no-delete rule was changed. No merge or deployment.
