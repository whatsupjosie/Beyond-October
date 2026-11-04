# PubCast test sandbox

One command builds a throwaway test environment, runs a defined set of real tests, writes a short report, and tells you what it could **not** test. The same script runs on the cloud sandbox and on a Windows laptop, so two reports can be compared and a difference between them points at a bug that exists in only one place.

It does not use GitHub Actions (see [QUALITY_STANDARDS.md](../../QUALITY_STANDARDS.md) section 7). Everything runs where you run it.

## Quick start

Linux or macOS, or the cloud sandbox:

```
python3 tools/sandbox/run_sandbox.py --tier fast
python3 tools/sandbox/run_sandbox.py --tier standard --capture
```

Windows PowerShell 5 (**not yet run on Windows; it has been run under PowerShell 7 on Linux, see the ledger at the bottom**):

```
powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Tier fast
powershell -ExecutionPolicy Bypass -File tools\sandbox\Test-PubCast.ps1 -Tier standard -Capture
```

A fresh cloud machine may need system tools first (ffmpeg, Xvfb, numpy for Blender, and optionally Blender, Rust and Firefox):

```
bash tools/sandbox/bootstrap_system.sh --check --all   # report only
bash tools/sandbox/bootstrap_system.sh --all           # install what is missing
```

The report appears in `.sandbox/reports/<time>-<label>-py<version>/`. Open `REPORT.md`; `report.json` is the same data for machines; `logs/` holds the full output of every step.

## Tiers

| Tier | What runs | Time on the 2-CPU cloud sandbox |
| --- | --- | --- |
| `fast` | Python syntax of all 365 source files, syntax of the 62 static scripts, 28 Node tests, the packaged-route preflight, 32 backend tests (studio switchers, media routes, recording guard, portable bundle) | about 20 seconds |
| `standard` | Everything in `fast`, plus the real launcher audit over loopback HTTP and 41 real-Chromium tests (2.5D studio, Foresight file workspace, walkable world, air-gapped UI) | about 8 minutes |
| `full` | Everything in `standard`, plus `npm ci`, `npm run test:node`, the whole pytest suite (2,167 tests), the Rust crate (tests and a release build of `ws_renderer`), a Blender smoke test and a Firefox smoke test | see the ledger |

`--extras rust,blender,firefox` adds those checks to any tier (the `full` tier always includes them). If a tool is missing the step is `SKIPPED` and marked `UNVERIFIED`, never `PASS`.

- **rust**: `cargo test --locked` in `rust_crate/` (32 unit tests), in a throwaway target folder outside the repository.
- **blender**: headless Blender imports `static/world/test_avatars/Husky.glb`, counts meshes, armatures and vertices, and renders a small frame with Cycles on the CPU; the frame must not be blank.
- **firefox**: real Firefox, driven over WebDriver (Selenium and geckodriver), loads the walkable-world page, checks software WebGL2, loads the 3D husky and takes a screenshot that must not be blank. This is a **smoke test**, not the Chromium test suite: Playwright cannot drive stock Firefox, so the existing tests cannot run there unchanged.

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
5. **Flaky tests are named, not hidden.** Failed tests are rerun alone (`--retries`, default 2). A test that then passes is reported `FLAKY`; the run ends `PASS WITH FLAKY TESTS` (exit 0, or exit 1 with `--strict`).
6. **Blender from apt has no denoiser.** A Cycles render with denoising on stops with "Build without OpenImageDenoiser", so the smoke test turns denoising off.
7. **Cargo must use its own compiler.** A Rust toolchain installed outside rustup would otherwise call the system rustup shim, which tries to download a toolchain and fails offline. The runner points `RUSTC` and `PATH` at the folder that holds the chosen `cargo`.
8. **Firefox needs a display for software WebGL.** Headless Firefox here has no WebGL2; under a virtual display (Xvfb) with Mesa software rendering it does. The runner starts Xvfb itself when there is no display.

## What this cannot test (always listed in every report)

- Real GPU speed. WebGL2 here is software-rendered through SwiftShader.
- A real microphone, camera or speakers. Browser fake devices and WebAudio meters only.
- Real phones. Phone-sized emulation only.
- Safari and WebKit. Playwright's WebKit download is not reachable from the cloud sandbox.
- Firefox beyond one smoke test. The 41 browser tests are Chromium-only.
- The Rust renderer as a running service. Only the crate's unit tests and a release build run, not a live `ws_renderer` session with a real client.
- Blender beyond import and a small Cycles render. No animation export, no EEVEE (no GPU), no add-ons.
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

Every line below was run on the cloud sandbox (Linux, 2 CPUs, 8 GB, no GPU, Chromium 153, Firefox 159, Node 22, Rust 1.97 and 1.99, Blender 4.0.2, Python 3.11/3.12/3.13) on 2026-11-01 against commit `bfbdcf0` plus this branch. Nothing here has been run on Windows.

### Tested

| What | Result |
| --- | --- |
| `fast` tier, clean room, repeated | PASS, 18 to 20 s, in every run after a fix to the syntax checker (the very first run failed because my checker mishandled a byte-order mark in `modules/voxel_block_kit.py`; the file itself is fine) |
| `fast` tier, warm (`--reuse`), twice | PASS, about 19 s |
| `fast` tier across Python 3.11.18, 3.12.3, 3.13.18 (`--matrix`) | PASS on all three; the comparison agrees on every result and notes only the Python version as inventory |
| Browser-test phase with real Chromium, run five times (four `standard` runs and the one inside the `full` run) | 41 of 41 passed in two runs; in the other three, 2 or 3 tests failed (see "Flaky tests"); two of those three were rescued by the rerun logic and one ran before reruns existed. About 420 to 490 s per `standard` run |
| **`full` tier, one clean-room run, 1,645 s (27 min)** | `PASS WITH FLAKY TESTS AND UNVERIFIED PARTS`. Whole pytest suite: 2,166 passed, 1 failed then passed on rerun, 2 skipped by design (the Alex Little One research-protocol tests only run when `ENABLE_ALEX_LITTLE_ONE=true`; I did not enable them). Browser tests: 2 flaky, passed on rerun. `npm ci` and 9 npm Node tests passed. Data guard clean |
| Rust crate, system toolchain (rustc 1.97) | `cargo test --locked`: 32 passed (23 in the library, 9 in `ws_renderer`); release build of `ws_renderer`: 61 s. 8 compiler warnings counted in the build log (unused imports and variables), not fixed |
| Rust crate, conda-forge toolchain (cargo 1.99.1), cold build | 32 passed in 48 s. This is the fallback for a machine with no Rust: the official Rust download host is blocked from the cloud sandbox but conda-forge is reachable |
| Blender 4.0.2 (apt) | Imports `Husky.glb` (2 meshes, 1 armature, 3,942 vertices) and renders a 192 by 144 frame with Cycles on the CPU. The frame was opened and looked at: the husky, lit, on black |
| Firefox 159 (conda-forge) driven over WebDriver | Software WebGL2 works under Xvfb; the walkable-world page loads, the 3D husky loads, and the screenshot was opened and looked at: Green Room with the husky standing by the couch. Headless Firefox without a display has no WebGL2 here, which is why the runner starts Xvfb. Firefox records WebM VP8/Opus only (no VP9, no MP4) |
| Playwright matching | Pinned 1.56.0 did not match Chromium 1243; in every clean-room run the runner installed 1.63.0 and the browser then launched |
| `--cold-cache` install | Works (about 10 s against about 0.3 s cached) |
| `--capture` | Real browser capture of the walkable world. The contact sheet was opened and inspected: the husky walks across the Writers' Room to the door and the "Which way?" prompt appears |
| The runner notices a failing test | A deliberately failing test gave step `FAIL`, run `FAIL`, exit code 1, and the test named in the report |
| Rerun logic | A test that failed once and passed on rerun was labelled `FLAKY` (not `PASS`), listed by name, exit code 0 |
| No-Chromium path | With the browser folder emptied, browser steps were `SKIPPED` as `UNVERIFIED` and the run ended `PASS WITH UNVERIFIED PARTS` |
| Data-pollution guard | A step that wrote a file into `data/` was blamed by name and no other step was; the real preflight, run without protection, modifies the Alex vessel file and writes 21 other files (restored and re-verified against the canonical hash) |
| `--compare` | Agreeing runs exit 0; a run with a step that failed in only one environment exits 3; setup steps, versions and browser build are noted but not counted as differences |
| `Test-PubCast.ps1` under **PowerShell 7.4.6 on Linux** | Parses with PowerShell's own parser (0 errors); no PowerShell-7-only syntax found by search; pure ASCII; ran the `fast` tier end to end; `-Matrix`, `-Compare` (comma form), `-Reuse`, `-Label` pass through; a bad `-Tier` and a one-value `-Compare` are rejected; no Python on PATH gives the message and exit 2; exit code 3 passes through |
| The Windows-only branches of `run_sandbox.py`, simulated | `Scripts\python.exe` path, the `py` launcher form, and the `%LOCALAPPDATA%` browser folder behave as intended. This is logic only, not Windows |
| `bootstrap_system.sh --check --all` | Runs and reports every tool present. The Rust, Firefox and PowerShell install commands were each run by hand and worked; the script's own install branches were not run |

### Not tested, or only partly

| What | Why it matters |
| --- | --- |
| **Windows PowerShell 5 itself** | PowerShell 7 ran the wrapper, but 5 is an older engine. I could not get PSScriptAnalyzer (its compatibility rule) because the PowerShell Gallery is blocked here. Expect, at worst, a small fix on the first real run; send the exact error. |
| **`run_sandbox.py` on real Windows** | Never run there. Only simulated, see above. |
| macOS | Never run. |
| Safari and WebKit | Not obtainable from here. Playwright's WebKit comes from a download host that is blocked. |
| The 41 browser tests in Firefox | They are Playwright tests and Playwright cannot drive stock Firefox. Only the one WebDriver smoke test runs there. Porting the tests is real work. |
| `ws_renderer` as a running service | Only unit tests and a build. A live session with a real client has not been run through the runner. |
| `--allow-browser-download`, `--playwright-version`, `--keep-venv`, `--strict` | Coded, not exercised. |
| `bootstrap_system.sh` install branches | Only `--check` was run through the script. |
| The Python matrix with browser tiers | Only the `fast` tier was run across versions. |
| The two skipped Alex Little One tests | Skipped by design. Whether to enable them is Josie's call. |
| Colab or Hugging Face hosting | Deliberately not built yet. |

### Flaky tests

**Recording tests: cause found and fixed (2026-11-04, integration branch).** Three tests in `tests/test_production25d_browser.py` (panic, multiple takes, failed storage) had failed at least once and then passed on rerun, always with "no media was recorded". Cause: each stopped the recording after a fixed delay (about 1.1 s). The browser's recorder hands over its first chunk only once it has encoded something, and on a busy machine that can come later than the delay, so the studio was stopped with nothing to save and reported "Recorder generated no video data". The tests now count non-empty recorder chunks (a read-only counter added in the test fixture) and wait for real media before stopping; the same wait was added to the recorder-error test and the reload-and-play test. Nothing in the studio itself was changed. Evidence: those five tests passed 30 of 30 runs on an idle machine, and 10 of 10 across two runs with both CPUs saturated; the old version of the tests, run the same way, failed 2 of 5 in one saturated run and passed 5 of 5 in the other. Real product behaviour that remains: a person who presses Stop within about a second or two of Record can get the "no video data" message instead of a saved take.

Still observed, not fixed:

- `tests/test_foresight_file_workspace.py::test_normal_2i_manuscript_saves_to_reach_and_each_save_is_a_new_revision` (failed once in one warm run)
- `tests/test_foresight_file_workspace.py::test_portable_save_as_and_reopen_uses_real_disk_without_vendor_picker` (failed once under full-suite load on the merged tree, passes alone)

A `FLAKY` result means "this test is unreliable here", not "this feature works". The tests were not changed; fixing them is separate work that needs Josie's go-ahead.
