# Primp and cream: executed Chromium acceptance

Date: November 9, 2026. Work branch: `gpt/primp-canvas-preparation-2026-11-07`. Unreleased; no main merge or deployment.

The prior WebGL execution blocker is closed for this Linux software-rendered browser. This is acceptance of the exercised authoring paths, not a claim of complete Primp, hardware performance, aesthetic approval, or a commercially ready makeup teaching application.

## RAN

Final restored-source rerun: **14 Chromium acceptance tests passed, zero skipped, zero failed**, in 194.93 seconds. One of these tests runs the existing **23-check browser foundation harness** and requires every check to pass; those 23 are nested checks, not 23 additional independent pytest tests.

**36 Node tests passed**, including strict file boundaries, exact layer/history behavior, island masks, prepared-source integrity, writer failure handling, and existing focused regressions.

Browser: Chromium **153.0.8010.0**, packaged in `@sparticuz/chromium` 153.0.0; Python Playwright **1.65.0**, pytest-playwright 0.10.0, pytest 9.2.0, Python 3.12.14. WebGL 2 uses ANGLE/SwiftShader software rendering. The smoke test launched the browser, clicked a local page, verified the changed output, and captured a screenshot before application testing.

Tests start the actual `main:app` in a child process, wait for `/health`, create a synthetic owner through the real setup API, and use its verified bearer session. Data, credentials, and browser profiles are temporary test resources. No real account or user library is used for application state. The host is restarted with its same test data and signing secret for the restart test. Production modules are served by the real host; only the foundation harness's QA files/fixture use test routing.

| Executed path | Required observable result |
| --- | --- |
| Manny and Sheila | Visible avatar pixels; face framing, warm lighting and pointer orbit change the rendered result. Original simple geometry is preserved; these are not newly authored expressive faces. |
| Fine paint | Real pointer stroke changes rendered pixels; saved layer is 2048 square and nonempty; embedded source bytes match exactly. |
| Undo/redo/compare | Ten actual pointer edits reverse and redo; comparison uses the original material; painted render returns unchanged. |
| Portable look | Download a real `.primp`, clear paint, reopen that file and compare rendered pixels. |
| GLB and image | Download painted GLB, import it and compare rendered pixels; downloaded PNG matches the canvas. |
| Recovery | Reload and recover identical paint; close/relaunch a persistent browser process and restart the actual host, then recover identical rendered paint. |
| Context loss | Real `WEBGL_lose_context` event disables graphics actions, preserves file saving, then restores the same painted render. |
| Mobile emulation | 390 × 844 viewport has no horizontal overflow; browser touch input paints and undo reverses it. Not a physical Android pass. |
| Imported rigged face | Face close-up, paint, hidden layer, zero opacity, restored opacity, another layer and powder all exercise rendered behavior. |
| Rejected import | Invalid GLB reports an error while preserving the painted avatar and undo. |
| Authentication expiry | Invalid session cannot overwrite the saved account recovery revision; portable save remains available. |
| Bounded repetition | Sixty edits leave ten undo entries within the 64 MiB history bound and keep a live graphics context. Not a prolonged-session/native-memory benchmark. |
| Browser file writer | Actual OPFS `FileSystemFileHandle` writer writes/closes and reads back exact bytes. The picker is supplied by the test: this does not verify the native OS chooser. |
| Accessibility | axe-core 4.11.1 WCAG A/AA-tagged scan has no reported violations, and selected keyboard toggles operate. This is not screen-reader/user acceptance or keyboard-only drawing support. |

Console and failed-request records are captured by the fixtures; unexpected page exceptions and failed transport requests fail instrumented mirror tests. Intentional invalid-token/import failures are exercised as negative cases. Two test-runner deprecation warnings remain (Starlette's AnyIO alias and a plugin fixture warning); neither is an application pass or failure.

## Fixes and diagnosis

`composeSurface` now selects the original imported map and material color for Before comparison and when all paint layers are hidden or have zero opacity. This prevents base-factor baking from affecting the original comparison view. Production interfaces and original source assets remain unchanged.

An initial strict render assertion found a one-code-value difference on fewer than 0.1% of pixels after preparing the hologram base texture. Linear material factors baked into 8-bit sRGB introduce quantization; this is not leftover paint. Only original-versus-prepared neutral comparisons permit a maximum one-code-value error on at most 0.1% of pixels. Painted redo, comparison, visibility on the imported face, portable reopen, GLB roundtrip, snapshot and restart checks require exact RGB pixel agreement. Exact editable-layer undo remains independently checked by the foundation/Node tests.

The direct Playwright browser CDN initially returned HTML instead of an archive. The fallback packaged headless Chromium passed real launch/WebGL smoke and application tests. After workspace maintenance reset the machine, system Chromium 156 failed to launch because its profile singleton Unix socket was unavailable in that execution boundary. The packaged headless Chromium succeeded again without adding the package's recommended broad insecure flag array. Browser binaries and lab dependencies are not shipped with Primp or installed at application startup.

## Cream workbench: separate result

The actual cream browser workflow passed: preview retry, stale-response rejection, 12-cell pointer application, wipe, tape, undo, project save/reopen, GLB download, 390-pixel reflow, and face-study views. No JavaScript page errors were recorded.

A clean installation exposed undeclared **SciPy** and **NetworkX** dependencies used by existing Trimesh validation/repair paths. The cream bundle now declares both. Its **132 existing tests passed** after correction; two new downloaded-GLB validator tests also passed.

The downloaded GLB initially failed a raw indexed-connectivity assertion because it deliberately duplicates positions for shading normals. A separate analysis mesh joined by EXACT coordinates is closed, consistently wound, and has positive volume: 166 triangles, 0.0000641159757792123 cubic metres. No coordinate rounding, hole filling, simplification or file rewriting is used. The browser workflow now checks the actual downloaded GLB this way, and a missing-triangle negative test verifies refusal. Geometry implementation and example assets were preserved.

The updated existing bundle includes the dependency fix, stronger export test, checksums, and its own detailed Chromium report. It does not bundle new browser screenshots or browser binaries.

## Reproduction

Install canonical `requirements.txt` and the separate `tests/primp_chromium/requirements.txt` into a test environment. Supply an installed Chromium path through `PLAYWRIGHT_CHROMIUM_EXECUTABLE` when not using Playwright's bundled browser, and an installed axe-core `axe.min.js` path through `AXE_CORE_PATH`. No real owner credentials are required.

Run `python -m pytest tests/primp_chromium --browser chromium --tracing retain-on-failure --screenshot only-on-failure --output <artifact-directory>`.

Tests launch their own real temporary host. The host and browser must run in the same execution boundary; separate terminal invocations can have separate network namespaces in this environment. Missing binaries or libraries are setup failures, never passing application checks.

## Remaining limits

- Physical phone/Windows behavior, actual pen devices, native OS save chooser, hardware GPU performance, sustained memory/thermal use, and screen-reader/user acceptance remain open.
- Software-rendered screenshots are observed evidence, not approval of lighting, anatomical detail, makeup quality, or every imported UV/seam layout.
- Dremel/continuous-cream sculpting and mesh-bake integration into Primp remain separate implementation work. No camera access, coaching, teaching library, product science, or instructional accuracy is established by these tests.
- Full PubCast studio regressions and unrelated optional audio/vision/renderer integrations were not accepted by this focused run. Their startup capability warnings remain separate from Primp's authoring result.
