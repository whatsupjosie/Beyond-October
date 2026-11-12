# Blackbox infrastructure — session ending handoff

Branch: `gpt/live-studio-setup-2026-11-09`. Work date: 2026-11-09.

## Result

Hardened the actual imported `blackbox_recorder/` package and its runtime/media
connections. The separate legacy root `blackbox_recorder.py` is unchanged.
Blackbox remains an external append-only witness: no player-menu review,
decoding, edit, or delete surface was added.

- Slow writes now emit a bounded performance warning instead of recursively
  generating warnings. A storage write failure latches further appends off;
  an explicit verified recorder reopen is required to resume.
- Recorder reopen validates the entire chain, sequence, session identity and
  complete final line before permitting append. Corrupt sources are retained.
- Runtime close/access/crash recording share a lifecycle lock; closed witnesses
  refuse late writes.
- PCM acknowledgements require both a flushed/fsynced WAV packet and its
  durable frame-range/SHA-256 ledger receipt. A failed receipt closes capture
  as failed and retains already written audio.
- Atomic capture sidecars persist clean/failed close state and WAV checksum.
  Recovery checks format, metadata, truncation and checksum; interrupted capture
  and malformed metadata remain visible instead of becoming healthy silently.
- Correct channel mappings cover runtime, capture, save/preserve, camera and
  encoded recording events. The canonical camera bridge journals changes
  synchronously before broadcast to preserve event ordering. Encoded takes
  journal upload start, abandonment and the existing completed-artifact receipt.
- Offline `tools/blackbox_inspect.py` validates ledger chains, PCM packet hashes
  and continuous frame ranges, and preserved-copy hashes/frame counts. It reports
  missing receipt-referenced media and uncatalogued WAVs. It exposes metadata
  and verification outcomes, not raw recordings or chat contents.

## Validation

Final focused regression: **76 passed**, 10.09 seconds. Covered event language,
runtime wiring, media failure/recovery, real HTTP/WebSocket capture, camera
broadcast ordering, encoded ingest, archive integrity and portable bundles.
The real HTTP test captures generated PCM, restarts the host, preserves an exact
sample range, verifies its ledger checksum, then proves alteration is detected.

Separate real Chromium 141.0.7390.37 test: **1 passed**, 20.90 seconds:
`tests/test_studio25d_archive_browser.py::test_completed_take_reopens_from_server_after_browser_and_host_restart`.
It records an actual browser take, restarts browser and host, reopens playback,
verifies the original bytes, and checks all session ledger chains plus matching
upload-start, artifact-hash and camera receipts.

`tools/blackbox_smoke.py` and `tools/blackbox_hardening_check.py` passed.
Existing pytest dependency deprecation warnings remain. This was not a full
repository test run. All fixtures used isolated temporary data; owner data and
credentials were not modified.

## Operator check

Stop the host for a stable snapshot; use the same Python environment as PubCast:

```sh
python tools/blackbox_inspect.py --data-dir /absolute/path/to/runtime-data
```

Exit 0 requires both integrity and complete supported PCM coverage. Historical
sidecars without a durable close marker are conservatively interrupted. Old
preserved copies without receipts are uncatalogued. Neither condition deletes
or repairs source data. Preserve a copy before investigating damaged files.

## Remaining work and practical limits

1. **Always-on production studio audio is not established.** The existing
   `static/blackbox_client.js` is loaded by the legacy Control page; production
   2.5D/director pages do not yet feed their live mix into this transport.
   Wire the actual production mix and exercise permission refusal, backgrounding,
   reconnect and source changes in Chromium and on Curtsey's Android phone.
   A running ledger/heartbeat must never be described as proof of audio capture.
2. Browser tests use generated audio, not the phone's physical microphone or a
   real multi-person production mix. Avatar animation was not evaluated here.
3. The offline inspector covers BBX/PCM/preserved WAVs; encoded WebM integrity
   is checked by the recording archive and browser test, not this CLI. It is not
   a complete inventory check for every PubCast event or media subsystem.
4. Hash chains and checksums detect corruption against retained receipts. They
   are not externally anchored signatures and do not prevent an attacker from
   rewriting an entire ledger and its media. Locks are in-process; do not attach
   multiple writer processes to the same ledger file.
5. No disk-full hardware test, forced OS kill/power-loss experiment, long-run
   retention/rotation capacity test, backup replication, or production workload
   latency measurement was performed. The configured compute budget is a target,
   not a measured guarantee. Camera journal fsync can delay a cut on slow storage.

These changes are committed on the work branch; they are not merged or deployed.
