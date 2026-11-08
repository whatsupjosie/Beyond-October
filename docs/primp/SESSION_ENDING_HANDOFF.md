# November 8 continuation

The current continuation is recorded in [GAP_CLOSURE_2026-11-08.md](GAP_CLOSURE_2026-11-08.md). The earlier report below is historical; its legacy-avatar, UV-mask, fixed-resolution, mixed-version recovery, account scoping, and host-dependency gaps have since been addressed. GPU/browser and physical-device acceptance remain open.

# Primp session ending handoff

2026-11-07. Branch: `gpt/primp-canvas-preparation-2026-11-07`.
Starting source: `bfbdcf0676c11163063ef369cd419b5667792cfe`.
This is an unreleased foundation, not a completed Primp product.

Latest follow-up: [Deep polish / troubleshooting round two](TROUBLESHOOTING_ROUND_2.md) records retained-buffer, import-boundary, staged-material, and project-budget repairs. The original session counts below are retained as history.

## Changed

Added the real surface-painting modules and digital mirror page under `static/primp/` and `static/primp.html`. Added Primp to `static/foresight_programs.js` and a link in `static/avatar_foundry.html`. Added executable checks under `tests/primp/` and a product/decision/release ledger in this directory. No prior source assets, profiles, geometry engine, or original design documents were overwritten. A pre-existing unrelated untracked avatar recovery file was left untouched.

## RAN

Environment: Linux, Node v24.22.1, Python 3.12.14. Browser: provided cloud Chromium; WebGL context unavailable. Test browser screenshots also timed out; no screenshot evidence is claimed.

- Syntax checks for app.mjs, model.mjs, core.mjs, and existing Counter program registry: exit 0.
- `node --test tests/primp/core.test.mjs tests/test_voxel_block_preview_client_node.js tests/test_foresight_file_close_node.js`: nine passing Node test entries, zero failing.
- Actual browser Canvas 2D / Three.js data / IndexedDB harness: twelve passed, zero failed on the final expanded harness. This is not a mocked browser and not a 3D render test.
- Actual existing GLB fixture: 52 bones, one skinned mesh, one animation. Export/reimport preserved these counts and painted texture; the harness added and preserved one morph target because the original fixture has none. Exported GLB: 1,226,792 bytes for that fixture.
- Exact layer PNG round trip and original source-byte round trip passed.
- Actual IndexedDB committed round trip and explicit aborted transaction preserving prior data passed.
- Raycast checks caught selected/occluded/hidden-surface boundaries; color checks cover skin factor neutralization, alpha preservation, and original texture resolution.
- Three history implementations, ten small strokes: snapshots 80 MiB, tile deltas approximately 0.44 MiB. Observed final sample: snapshot capture 43.5 ms, replay reconstruction 1.0 ms, tile capture 0.9 ms. These are synthetic-fixture observations in this browser, not phone performance or rendering benchmarks.
- Transparent-edge blend comparison: straight RGB red approximately 24.4; premultiplied kernel red 220; browser blur red 219 / alpha 28, from input red 220.
- `git diff --check`: clean at verification.

## Corrections during review

Preserved original skin texture dimensions rather than reducing them to the paint atlas size. Baked original material factors in linear light and kept material color neutral above that base, preventing skin tint from multiplying every cosmetic. Preserved transparent pixels. Replaced a color-smear approximation with an explicit alpha-aware softening kernel. Extracted the model boundary for real runtime tests. Rejected painting hidden or occluded surfaces. Rejected unsupported UV channels instead of pretending all channel layouts work. Stopped secondary pointers from starting orbit during paint. Separated graphics-context health from operation busy state. Made import controls keyboard focusable. Coalesced viewport renders per animation frame. Prevented an outdated recovery completion from reporting the current document as saved. Restored the after-state for avatar export even while the viewer compares the before-state. Removed a blanket exporter texture-size cap that could alter untouched textures. Avoided allocating a paint surface on a missed pointer hit, used original texture transforms before the first stroke, and released decoded PNG strings instead of retaining them alongside layer canvases.

## WROTE, NOT ACCEPTED THROUGH THE FULL UI

Viewport/face framing, pointer/touch painting on the rendered avatar, lighting changes, before/after button, complete .primp UI reopening, recovery button/restart, and UI download/export behavior. Their supporting paths have unit/browser-data evidence, but end-to-end viewport acceptance is blocked by WebGL context creation. Counter and Foundry links have source/syntax evidence, not a full host acceptance run.

## UNKNOWN / remaining work

1. Obtain an execution environment that supplies a functioning WebGL context and run complete UI acceptance; do not replace the renderer with a picture or mark it ready from the data harness.
2. Add visual tests for avatar deformation, UV island/overlap behavior, non-square/transformed textures, material groups, eye/lip target selection, and lighting across varied skin tones. UV attachment comparison is geometric, not a fully rendered three-candidate contest.
3. Address UV-island edge isolation, detail resolution policy, and supported glTF extension fidelity before market release.
4. Test real device memory/performance, touch/pen, keyboard/screen-reader paths, interrupted saves, browser restarts, context recovery, and cross-tab/profile recovery conflicts.
5. Run the authenticated PubCast host and Counter/Foundry integration acceptance, then appropriate wider regressions.
6. Continue three-solution comparisons for the remaining major features, with measured fixtures and explicit pass/reject reasons. Do not call the whole program complete.
7. Compile and review makeup lessons explaining purpose/proportion/contrast and adaptations to actual supplies, tone, undertone, and lighting. No unsourced lesson catalogue is shipped.
8. Evaluate permissioned camera capture, task-specific landmark feedback, and human/trained-model alternatives separately. Do not infer pressure, contact, perfect grip, or a single correct aesthetic from landmarks alone.
9. Integrate audited continuous cream / Dremel geometry authoring only after protecting UVs, weights, and expressions and validating combined undo.

No owner credentials or aesthetic decision was needed for this implementation. The present blocker is the available browser graphics capability, not missing permission from the owner. No production deployment, main merge, or release approval.
