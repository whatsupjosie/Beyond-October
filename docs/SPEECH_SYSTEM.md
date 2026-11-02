# Local speech commissioning — PC-035

Agent: `Codex / ChatGPT Work / speech-system-2026-11-01`. Branch: `gpt-work`.
The original recovery commit is `123474459c472fb449d3fd56a07331f4650ae69e`.
Executed evidence is in `evidence/speech-system-2026-11-01/`.

## Working scope and limits

Local English dictation and generated English speech now use the existing host,
auth identity, writing/chat controls and program mixer. Recognition uses
faster-whisper tiny.en on CPU/int8. Neural speech uses quantized Kokoro on CPU
with twenty-eight configurable English voice styles. These are technical voice
choices, not final casting of the owner's characters. Model/source revisions and
every downloaded source hash are pinned in `tools/speech_assets.json`.

The real Linux/Python 3.12/Chromium test records a generated microphone fixture,
recognizes the original sentence, presents an editable review, inserts only on
the user's click, reads through 2i, generates another selected voice, records the
program mixer, independently decodes the recording, stops playback/work, and
reopens saved choices after browser and host restart. This is generated test
speech through a real browser capture pipeline, not physical-microphone evidence.

**Native Windows/PowerShell 5, physical devices, varied human speech/noisy rooms,
non-English recognition, sustained sessions and sample-accurate lip sync remain
unverified.** Windows SAPI and the preserved explicit local XTTS adapter are
unverified optional paths. Linux's basic FFmpeg/flite fallback was actually run.
The browser's optional native speech mode is explicitly labeled listening-only:
its output does not enter program recordings. Speech does not replace Claude's
motion/facial/performance capture. Existing external Larynx/Piper behavior at
`/api/inference/tts` remains a separate legacy integration; these browser controls
use `/api/tts/synthesize`.

## Explicit installation

Application startup and inference never download a speech model. Core startup
works without the optional speech packages or weights; status identifies what is
missing. Default installation lives inside the launcher's chosen data directory.
External path overrides in `.env.example` require their own backup coverage.

These commands are PowerShell 5 syntax; **they have not been run on Windows**.
Use the project's Python environment and the exact data directory used at launch.
The download step deliberately accesses Hugging Face once; it is not a startup
step. The example creates a new local environment only when one is needed.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-speech.txt
.\.venv\Scripts\python.exe tools\speech_setup.py --data-dir C:\PubCastData
.\.venv\Scripts\python.exe tools\speech_setup.py --data-dir C:\PubCastData --verify
.\.venv\Scripts\python.exe run_reach.py --data-dir C:\PubCastData --no-legacy-2i
```

Linux executed the same Python tool with POSIX paths. `--source-dir` accepts a
previously downloaded source directory for **one** `--model kokoro` or
`--model whisper-tiny.en`, checks the pinned hashes, and installs without a
network connection. `--verify` is entirely local. Repeating installation verifies
an existing installation; it never overwrites it. A mismatched or interrupted
installation fails explicitly; preserve that directory and install in a new data
root or configure a verified external model path rather than deleting owner data.

Kokoro's raw English style arrays are repacked losslessly into the NPZ container
expected by kokoro-onnx. `INSTALL.json` retains repository/revision, source hashes
and output hashes. Models are external runtime inputs and are not committed to
Git. The source model cards carry MIT (Whisper) and Apache-2.0 (Kokoro) provenance;
upstream code licenses remain separate. Source cards are retained with installs.

Primary sources: [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx),
[pinned Kokoro conversion](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/tree/1939ad2a8e416c0acfeecc08a694d14ef25f2231),
[original Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M).

## Runtime contract

`GET /api/stt/status`, `/api/tts/status`, `/api/tts/voices` distinguish configured,
available, loaded, ready, busy and failed states. Constructors do not prove model
operation. Models load only in their owned worker's first request. A single
bounded request runs per engine; contention returns 429 without an unbounded
queue. Recognition times out after ninety seconds; generation after 150 seconds.
Cancellation terminates the owned worker and native child process group; the next
request starts a new worker. Idle shutdown first gives the provider a graceful
exit. Input text and transcripts are not logged by the speech worker.

The normal authenticated launcher requires a verified token for all speech
routes. Explicit relaxed developer auth follows the repository's shared identity
policy. Synthesis/transcription each permit sixty requests/minute per identity.
Quota keys are bounded. `reach_auth.js` already injects same-origin bearer auth;
the shared speech client also supplies it when present. The original issue claim
incorrectly called the frontend fetch omission an auth defect; the actual defect
was that the original server routes lacked identity dependencies.

Recognition accepts supported audio containers up to eight MiB and sixty decoded
seconds. The browser finishes at fifty-five seconds. The decoder reads bytes,
rejects playlists/URLs, decodes only audio, bounds actual sample count and returns
mono 16 kHz float32 to Whisper. This also avoids faster-whisper 1.2.1's incompatible
`metadata_errors` file-open argument with PyAV 19. Word/segment times are model
estimates, not a phoneme alignment or lip-sync promise. Raw and multipart uploads
are tested. Missing dependencies/models return 503, malformed media 415, limits
413, invalid settings 400, and busy work 429 with Retry-After.

Generation accepts at most two thousand characters per request, finite speed
0.7–1.5, validated English language and catalogue voice IDs. Browser read-aloud
splits longer text into bounded passages without modifying the manuscript. WAV
headers, decoded frame count, duration, byte count and finite neural samples are
validated. `X-Duration`, `X-Audio-Samples` and `X-Sample-Rate` derive from the actual
WAV, replacing the earlier byte-count estimate. Playback enters the existing
`PubcastProgramAudio` dialogue bus and its capture output. Stop, dialogue mute,
room interruption and page exit cancel pending playback; generation fences stop
late results from starting sound. Object URLs and microphone tracks are released.

`pubcast:speech-start` / `pubcast:speech-end` carry character/voice/provider,
sample count/rate, exact WAV duration and observed browser playback times. These
are an explicit integration seam for capture work, not a second mixer or an
avatar animation controller. No character canon or actor controller was changed.

`GET`/`PUT /api/tts/preferences` uses the verified caller's identity and a SQLite
revision check. Stale writes return 409. The catalogue voice, speed and language
survive restart in `DATA/speech/preferences.sqlite` and the offline data checkpoint.
Cross-owner isolation and checkpoint restoration are tested. Existing text is
retained throughout dictation; review supports Insert and Discard, with no autosend.

## Observed corrections and remaining concerns

Three approaches were compared: native/browser speech, local XTTS/Piper, and
CPU Whisper plus Kokoro. Native browser speech cannot feed the capture mixer;
XTTS adds a much heavier optional runtime and requires an explicit existing model;
the local neural pair gave actual CPU audio/recognition with pinned assets and
bounded workers. Native flite remains an explicit basic fallback where present.

A real disconnect test failed before correction: Starlette's zero-time
`is_disconnected` cancellation could cancel its middleware channel before a
disconnect arrived. The worker supervisor now awaits the receive channel after
the route has consumed its body. The same HTTP cancellation and subsequent fresh
request pass, including clean host shutdown.

The existing control page and its base template both included `ui.js`, toggling
the drawer twice per click. It now binds once; controls wrap within the existing
drawer. This headless Chromium environment's CSS transition clock remained at
zero, so browser acceptance explicitly uses the supported reduced-motion setting
and the new reduced-motion drawer rule. Ordinary compositor animation is not
claimed verified by that run.

One reload also produced an existing `modules/blackbox_routes.py:146` socket-close
`WebSocketDisconnect` log. Speech completed and the host shut down; this separate
PC-024 lifecycle issue is recorded, not silently counted as fixed. Optional native
renderer bridge connection failures likewise remain outside speech acceptance.
No main merge, deployment, GitHub Actions or connection to an unidentified remote
sandbox occurred. The two sandbox runner definitions do not provide remote access
addresses; these runs used isolated local data and the actual local host/browser.
