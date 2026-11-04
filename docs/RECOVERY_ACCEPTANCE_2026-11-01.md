# Offline recovery: executed application acceptance

Signed: **Codex / ChatGPT Work / recovery-completion-2026-11-01**.
Branch: `gpt-work`; starting source `1e33789ba82d231384b04063b1b68325ca94df4c`.
Work: [PC-003; related PC-006](https://github.com/whatsupjosie/Beyond-October/issues/1).

## Actual outcome

Offline host-data recovery is **verified in the named Linux environment** through
the real application and browser. Windows/PowerShell 5 and the other limits below
remain open; this is not an unqualified cross-platform completion declaration.

The test launches the actual `run_reach.py` process with enforced authentication
and its own persisted keys. It creates an owner through the real API and saves a
2i manuscript, workspace file, conversation, PubPartner echo exchange, Counter
layout and Bella progress. A real two-second VP9/Opus test-pattern clip is produced
with FFmpeg, exported through RecordingService and imported through the real host.
It is a deliberately generated media fixture, not a physical camera/microphone take.

After a clean shutdown, the actual checkpoint CLI creates and verifies the archive.
The old data directory is renamed away, leaving its former path nonexistent.
The CLI restores into a new root. The real launcher starts there on a different
port, proving that reads cannot accidentally succeed from the old location.

The checks then verify:

- Setup remains complete; a wrong password and anonymous manuscript request fail.
- The original JWT remains valid and an encrypted test credential decrypts with
  the restored key. Test secrets are generated only for this disposable run.
- Original document, conversation, workspace, PubPartner exchange, layout and
  progress content return from the real authenticated APIs.
- A fresh Chromium context signs in through the actual login page, opens the
  original manuscript through 2i's shelf and reads its exact committed text.
- Gallery opens the preserved recording and its real video element plays with
  decoded 320×180 frames and advancing time. Downloaded source bytes match exactly.
- External browser requests are blocked during that browser workflow.
- Packaged seed data has the same file inventory and hashes after the run.

## Defect found and fixed during the exercise

The WebM export selected libopus but inherited a production AAC profile's
320 kb/s audio setting. Actual mono encoding failed with FFmpeg's explicit
500–256,000 b/s supported range. Original media remained available, but no
derived clip was produced. The dedicated reproduction failed on the prior code.

`RecordingService` now probes the actual audio channel count when a libopus
export requests more than the mono limit. It applies the corresponding encoder
bound only where required and records the adjustment in the manifest. Stereo
retains the requested 320 kb/s. Source media is still archived byte for byte;
the derived file remains explicitly marked `source_master: false`.

If ffprobe is unavailable or cannot measure the source, the requested setting
is retained and a warning identifies that limitation; existing conversion-failure
reporting remains active. No guessed channel count or source rewriting occurs.

Both mono and stereo regressions produce a real derived clip, decode it with
FFmpeg, and compare the packaged original with the exact input bytes.

## RAN

Environment: Linux, Python 3.12.14, real Chromium 141.0.7390.37/Playwright 1.56.0,
FastAPI 0.115.14 and FFmpeg. The host dependencies were installed into an isolated
virtual environment. Versions and source fingerprints accompany the logs.

| Command scope | Observed result |
| --- | --- |
| `test_data_checkpoint.py`, `test_data_checkpoint_host_recovery.py`, `test_recording_portable_bundle.py` | **49 passed, 0 skipped**, 14.56 s; 16 supporting subtests also passed |
| `test_shared_studio_switchers.py`, `test_studio25d_media_routes.py`, `test_studio25d_recording_guard.py` | **17 passed, 0 skipped**, 1.52 s |

The two scopes contain different test files. They do not replace a full-suite run.
The exact host result, logs, XML and production-bug reproduction are under
`evidence/recovery-completion-2026-11-01/`.

Harness corrections during development: the credential class and two API argument/
route names were corrected to their real interfaces; Gallery playback was changed
to invoke Play because its normal modal does not autoplay. No product behavior
was changed to make those mistaken harness assumptions pass.

## Remaining limits and handoff

**Not executed:** native Windows/PowerShell 5; physical microphone/camera/speakers;
production-length or quota/power-loss recovery; browser-only IndexedDB; independent
runtime roots and external assets/secrets; full repository suite; separate remote
sandbox machines. Claude's reusable runner was inspected from `claude-work`, but
the runner code is not evidence of access to a separate persistent machine.

The real Windows gate stays open on the master list. The archive remains private,
unencrypted and limited to its explicitly selected offline host-data directory.
No main merge, deployment, GitHub Actions run or product launch occurred.

Next assigned system: speech-to-text/text-to-speech, queued under GPT ownership.
Motion/facial/performance capture remains Claude's owner-reported assignment.
