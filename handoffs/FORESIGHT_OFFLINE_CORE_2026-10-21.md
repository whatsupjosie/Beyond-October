# Foresight offline file and code workspace — current handoff

This is the current implementation report. Earlier same-day audits remain historical. It is an update to the existing October source, baseline 82ebf26755d3706f8d4d7d75d823bb73f4d1b07e. It is not an installation into the user's computer or a full source distribution. No remote push was made.

## Governing constraints

Essential file work is local. Google services, cloud accounts, Chromium, Playwright and the optional Node utilities are not runtime prerequisites for opening and editing text. Browser tests use Playwright as development tooling only. Files use documented formats and ordinary folders; integrations must remain replaceable. The tray hosts existing programs, including the actual 2i v22 editor.

## Working capabilities and evidence

| Capability | Current behavior |
| --- | --- |
| Text, Markdown, XML and scripts | Open in 2i, edit, native undo/copy/paste, keep original, save working copy, export and reopen |
| Save As / folders | Save to ordinary files under the user's local PubCast workspace, including nested folders, through a browser-independent local API |
| Save existing local file | Subsequent Save updates the chosen workspace file; content revisions reject conflicting replacements |
| Native manuscripts | Both normal 2i and file-mode 2i can save complete .2i manuscript state to local folders |
| Optional device picker | Save to device remains available where supported; download fallback works without that picker |
| Reopen after restart | Disk files survive router restart and are listed under Local PubCast folders in Saved files; browser working copies remain available too |
| DOCX | Local main-body/table text reading; native ZIP/XML DOCX text-copy export verified by an independent reader; no Word or Google Docs required |
| Other documents | Existing local ODT/PPTX/XLSX/PDF text extraction retained, with explicit fidelity limits; original bytes remain recoverable |
| Images | Rotate, crop, save PNG working copy, export and reopen inside 2i; original retained; cancelled crop leaves original output intact |
| Audio/media | Existing browser media playback retained; a local WAV was decoded, played muted and reopened with external requests blocked |
| Coding | Local Python syntax check without execution; explicit Run Python opens an owned local process console with stdout, stdin, traceback, exit status and Stop |
| Terminal | Existing owner-only host shell console; streamed standard input/output; process-group cleanup on disconnect and Quit |
| Account access | Reuses the local Reach authentication adapter and login/setup pages; no Google sign-in. Login and served 2i font requests no longer contact Google |
| Startup / Quit | Normal startup never installs optional Node dependencies. Explicit --install-legacy-2i is required to permit that download. Supervised authenticated Quit exits Reach and its owned consoles |

## Independence checks

- The 2i Google Fonts import and login-page Google Fonts link were removed. Local/system font fallbacks remain.
- Ordinary file-mode opening no longer initiates automatic collaboration checks or periodic manuscript submission. Explicit collaboration controls remain available.
- Browser tests abort external requests and fail if any were attempted. All tested file workflows passed that check.
- Tests disable showSaveFilePicker; local-folder Save As and later Save still write actual disk files.
- Native DOCX export was tested with the external docx writer module unavailable. The writer now uses standard-library ZIP/XML; python-docx is a development compatibility oracle only.
- Core runtime requirements do not include Playwright or Chromium. Browser binaries used for verification are not installed or launched by PubCast.
- Optional Node-service startup was tested with installer execution forbidden. Already-installed utilities remain usable; their absence does not block the native file workflow.

## Verification

- Latest functional suite: **27 passed** across workspace files, document formats, owned host controls and browser file workflows. This includes real disk persistence/restart, ownership isolation, stale-write conflicts, local syntax checking, actual Python execution/traceback, media reopening and native 2i manuscript saving, and preservation of manuscript titles and extension metadata.
- Related integration suite: **17 passed** for existing Foresight wiring, cohesive program routes, front door and real Reach startup. These are separate tests from the functional suite.
- Real launcher/HTTP audit passed: default offline-safe startup, page/assets, authentication, local disk save/readback, Python syntax API and supervised exit with code zero.
- JavaScript syntax, Python compilation, targeted Ruff checks and patch whitespace checks pass. The inherited Starlette AnyIO deprecation warning remains.
- The most recent broader Counter regression remains **87 passed, 1 failed**: unchanged physics timing measured 20.19 ms against its 16 ms budget. It was not loosened or hidden and no new physics optimization was undertaken in this pass.
- Firefox verification was attempted but did not become usable in this sandbox and was interrupted. It is not reported as passed. The passing browser tests establish behavior with the vendor-specific picker absent; a real Firefox/Windows workstation check is still required.

Functional command:
`python -m pytest -q tests/test_foresight_workspace.py tests/test_foresight_file_formats.py tests/test_foresight_host_tools.py tests/test_foresight_file_workspace.py`

Related integration command:
`python -m pytest -q tests/test_foresight_8787_wiring.py tests/test_foresight_cohesive_program.py tests/test_foresight_front_door.py tests/test_foresight_reach_runtime.py`

Launcher command: `python tools/foresight_checks/audit_launcher.py`

## Boundaries and remaining work

- Internet browsing remains the existing embedded webpage plus external-browser fallback. Sites that reject embedding still require the fallback. No compulsory Chrome/Chromium engine or unrestricted page proxy was added.
- Online Google Docs/Drive access and writeback remain optional integration work requiring runtime account authorization. Downloaded supported document files are readable locally. A .gdoc shortcut is a pointer, not its document contents.
- DOCX text copies do not preserve Word layout, images, headers, footers or footnotes. Spreadsheet formulas are text, not recalculated spreadsheets. Legacy .doc/.xls/.ppt and RTF conversion, PDF OCR/annotation and advanced media editing remain unsupported here; originals remain available.
- The shell console is useful for coding and troubleshooting but is not a full TTY emulator or breakpoint debugger. The Python runner executes only after explicit owner action; syntax checking does not execute source.
- Local folder paths are relative to each authenticated user's PubCast data workspace. This is a real disk folder on the Reach host. Arbitrary host folders can be reached through supported device-saving/downloading workflows; native OS picker permissions remain unverified on the user's machine.
- Browser recovery belongs to the browser profile; it is not account-isolated storage for a shared profile. Local disk folders are separated by authenticated identity.
- Browser recovery is not a substitute for exporting or saving important work to disk. Pending normal-2i recovery now prompts before leaving; asynchronous browser shutdown cannot be certified for every platform.
- Studio, PubPartner, PubWorld and control-room pages remain hosted by their existing routes. Physical camera/audio/GPU/model and full production workflow commissioning requires the actual workstation. Route availability does not certify those subsystems.
- The animation-viewer question and Performance/protected-background-task proposal remain deferred in PUBCAST_DEFERRED_FEATURES.md. They were not allowed to displace this work.

## Apply exactly one patch

Back up or preserve the current git state first. Use the patch matching the installed source:

1. `changes.patch`: original upstream baseline 82ebf26755d3706f8d4d7d75d823bb73f4d1b07e.
2. `changes-from-audited-update.patch`: earlier audited Counter update with the 74-test report.
3. `changes-from-file-workspace-update.patch`: immediately preceding file-workspace update with the 17-new-test report.

Run `git apply --check PATH_TO_PATCH`, then `git apply PATH_TO_PATCH`. Do not apply multiple patches. Conflicts in a newer repository must be reconciled, not overwritten. All supplied patches were actually applied to their matching snapshots and resulting changed files compared byte-for-byte.

Install runtime dependencies with `python -m pip install -r requirements.txt` during setup; normal application use does not run an installer. Launch `python run_reach.py --start-page foresight-counter`. First-run local account setup uses /login. In a blank tray choose Import, or use File > Open. Saved files includes both working copies and local folder files. Development > Host shell opens the console; Python files also expose Check Python and Run Python.

For development verification only, install requirements-dev.txt and the local browser needed by the test runner. Those tools are not runtime prerequisites.
