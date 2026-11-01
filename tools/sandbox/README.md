# PubCast test sandbox

One command builds a throwaway test environment, runs a defined set of real tests, writes a short report, and tells you what it could **not** test. The same script runs on the cloud sandbox and on a Windows laptop, so two reports can be compared and a difference between them points at a bug that exists in only one place.

It does not use GitHub Actions (see [QUALITY_STANDARDS.md](../../QUALITY_STANDARDS.md) section 7). Everything runs where you run it.

## Quick start

Linux or macOS, or the cloud sandbox:

```
python3 tools/sandbox/run_sandbox.py --tier fast
python3 tools/sandbox/run_sandbox.py --tier standard --capture
```

Windows PowerShell 5 (**unverified on Windows, see the ledger at the bottom**):

```
powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Tier fast
powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Tier standard -Capture
```

A fresh cloud machine may need system packages first (ffmpeg, Xvfb, numpy for Blender, optionally Blender):

```
bash tools/sandbox/bootstrap_system.sh --check     # report only
bash tools/sandbox/bootstrap_system.sh --blender   # install what is missing
```

The report appears in `.sandbox/reports/<time>-<label>-py<version>/`. Open `REPORT.md`; `report.json` is the same data for machines; `logs/` holds the full output of every step.

## Tiers

| Tier | What runs | Time on the 2-CPU cloud sandbox |
| --- | --- | --- |
| `fast` | Python syntax of all 365 source files, syntax of the 62 static scripts, 28 Node tests, the packaged-route preflight, 32 backend tests (studio switchers, media routes, recording guard, portable bundle) | about 20 seconds |
| `standard` | Everything in `fast`, plus the real launcher audit over loopback HTTP and 41 real-Chromium tests (2.5D studio, Foresight file workspace, walkable world, air-gapped UI) | about 8 minutes |
| `full` | Everything in `standard`, plus `npm ci`, `npm run test:node` and the whole pytest suite (2,167 tests) | 15 to 25 minutes (not yet run through this runner, see ledger) |

`--capture` adds a real-browser capture of the walkable world (your husky walking across a room) and builds a contact sheet, `capture/motion_strip.jpg`, from the recorded video so motion can be inspected without playing a video.

## Clean room, warm, matrix, compare

- **Clean room (default).** A brand new virtual environment is built for every run and deleted afterwards. Package downloads are cached unless you add `--cold-cache`, which bypasses the cache so the install really starts from nothing.
- **Warm (`--reuse`).** Reuses `.sandbox/venv-<version>`. Faster; can hide a dependency that only worked because it was already installed. Run clean-room before you trust a result.
- **Python matrix (`--matrix 3.11,3.12,3.13`).** Runs the chosen tier once per Python and compares them. Python 3.12 is the project's target; the others are early warning.
- **Compare two machines.** Run the same tier with a label on each machine, copy the two `report.json` files (or whole report folders) to one place, then:

```
python3 tools/sandbox/run_sandbox.py --compare laptop-report-folder cloud-report-folder
```

Differences in *results* (a step that passes on one machine and fails on the other, or a test that fails in only one) are reported as `DIFFERENT` and the command exits with code 3. Differences in *inventory* (Python version, browser build, GPU) are listed but expected.

Exit codes for a normal run: 0 all steps passed (unverified parts, if any, are named in the report), 1 at least one step failed.

## What the runner guards against

These each cost real time before this existed:

1. **Playwright and Chromium must be the same generation.** `requirements-dev.txt` pins Playwright 1.56.0 but the machine may carry a newer Chromium. If the browser will not launch, the runner installs the Playwright release that matches the Chromium already on disk (table `KNOWN_PLAYWRIGHT_FOR_CHROMIUM` in the script; extend it when you meet a new pairing) and proves the match by launching the browser. It downloads a browser only if you pass `--allow-browser-download`.
2. **Starting the app must not write into the repository.** `tools/workbench_preflight.py` says it is read-only, but it starts the real app, which writes databases, a master key, Blackbox files and **modifies the canonical Alex vessel**. The runner gives every app-running step its own disposable copy of `data/` (the same approach as `conftest.py`), and a final `repo-data-clean` step fails the run if anything under `data/` changed. If it ever fails, the report names the step and prints the cleanup command.
3. **Skips are not passes.** If any pytest step reports skipped tests, or the browser cannot launch, the overall result becomes `PASS WITH UNVERIFIED PARTS`, never plain `PASS`.
4. **A byte-order mark in a source file is not a syntax error.** The syntax check compiles bytes the way Python does.

## What this cannot test (always listed in every report)

- Real GPU speed. WebGL2 here is software-rendered through SwiftShader.
- A real microphone, camera or speakers. Browser fake devices and WebAudio meters only.
- Real phones. Phone-sized emulation only.
- Firefox and Safari. Chromium only.
- A local AI model with real weights. None ship in the repository.
- A real DaVinci Resolve import and relink.
- Windows and PowerShell 5 behavior when the run is on Linux.
- A second physical machine, long soak runs, network partitions.
- H.264 MP4 recording. Chromium here records WebM (VP9/Opus); the probe in each report says whether MP4 is supported.

## Adding a test

Put the test file in `tests/`, then add it to `FAST_PY_TESTS`, `BROWSER_PY_TESTS` or `NODE_TESTS` near the top of `run_sandbox.py`. Do not add a test to a tier without running it first and recording the result.

## Files

| File | Purpose |
| --- | --- |
| `run_sandbox.py` | The runner. Standard library only. All real logic. |
| `Test-PubCast.ps1` | Windows PowerShell 5 wrapper: finds a real Python, passes arguments through. |
| `bootstrap_system.sh` | One-time system packages on a fresh Debian or Ubuntu machine. |

## Verification ledger

Every line below was run on the cloud sandbox (Linux, 2 CPUs, 8 GB, no GPU, Chromium 153, Node 22, Python 3.11/3.12/3.13) on 2026-11-01 against commit `bfbdcf0` plus this branch. Nothing here has been run on Windows.

### Tested

| What | Result |
| --- | --- |
| `fast` tier, clean room, repeated | PASS, 18 to 20 s, in every run after a fix to the syntax checker (the very first run failed because my checker mishandled a byte-order mark in `modules/voxel_block_kit.py`; the file itself is fine) |
| `fast` tier, warm (`--reuse`), twice | PASS, about 19 s |
| `fast` tier across Python 3.11.18, 3.12.3, 3.13.18 (`--matrix`) | PASS on all three; the comparison agrees on every result and notes only the Python version as inventory |
| `standard` tier, four complete runs (three clean room, one warm) | 41 of 41 browser tests passed in two clean-room runs; one clean-room run failed 3 of 41 (before reruns existed); the warm run had 2 tests that failed and then passed on rerun. See "Flaky tests" below. About 420 to 490 s each |
| Playwright matching | Pinned 1.56.0 did not match Chromium 1243; in every clean-room run the runner installed 1.63.0 and the browser then launched |
| `--cold-cache` install | Works (about 10 s against about 0.3 s cached) |
| `--capture` | Real browser capture of the walkable world. The contact sheet was opened and inspected: the husky walks across the Writers' Room to the door and the "Which way?" prompt appears |
| The runner notices a failing test | A deliberately failing test gave step `FAIL`, run `FAIL`, exit code 1, and the test named in the report |
| Rerun logic | A test that failed once and passed on rerun was labelled `FLAKY` (not `PASS`), listed by name, exit code 0 |
| No-Chromium path | With the browser folder emptied, browser steps were `SKIPPED` as `UNVERIFIED` and the run ended `PASS WITH UNVERIFIED PARTS` |
| Data-pollution guard | A step that wrote a file into `data/` was blamed by name and no other step was; the real preflight, run without protection, modifies the Alex vessel file and writes 21 other files (restored and re-verified against the canonical hash) |
| `--compare` | Agreeing runs exit 0; a run with a step that failed in only one environment exits 3; setup steps, versions and browser build are noted but not counted as differences |
| `bootstrap_system.sh --check` | Runs and reports present tools (everything was already installed) |

### Not tested, or only partly

| What | Why it matters |
| --- | --- |
| **`Test-PubCast.ps1` on Windows PowerShell 5** | Never run. It was written without a PowerShell to try it on. Expect to fix something on the first run, and send the exact error. |
| **`run_sandbox.py` on Windows** | Never run there. The Windows branches (`Scripts\python.exe`, the `py` launcher, `%LOCALAPPDATA%` browser folder) are unexercised. |
| macOS | Never run. |
| `full` tier through this runner | The full pytest suite and `npm ci` were run by hand earlier in this project, not through the runner. |
| `--allow-browser-download`, `--playwright-version`, `--keep-venv`, `--strict` | Coded, not exercised. |
| `bootstrap_system.sh` installing packages | Only `--check` was run; the install path is unexercised. |
| The Python matrix with browser tiers | Only the `fast` tier was run across versions. |
| Colab or Hugging Face hosting | Deliberately not built yet. |

### Flaky tests (observed, not fixed)

Four tests failed at least once and then passed when rerun alone. The first three are recording tests and in each the symptom was that no media was recorded. In five direct repeats of just those three tests (no sandbox involved), two repeats passed fully and three each had one failure, a different test each time. For the panic test, a probe earlier in this project showed the recorder produces no data when the panic comes about two seconds or less after the recording starts, so that test lacks a wait for the first data. For the other two recording tests the symptom looks the same but the cause is **not established**, and for the file-workspace test (seen once) nothing is established.

- `tests/test_production25d_browser.py::test_remote_panic_stops_real_capture_blacks_program_and_silences_audio`
- `tests/test_production25d_browser.py::test_multiple_takes_keep_original_media_bytes`
- `tests/test_production25d_browser.py::test_failed_storage_keeps_a_downloadable_take_and_retries`
- `tests/test_foresight_file_workspace.py::test_normal_2i_manuscript_saves_to_reach_and_each_save_is_a_new_revision` (once, not yet repeated)

A `FLAKY` result means "this test is unreliable here", not "this feature works". The tests were not changed; fixing them is separate work that needs Josie's go-ahead.
