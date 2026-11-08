# Primp: makeup tools and digital mirror

Latest audit: [Deep polish / round two](TROUBLESHOOTING_ROUND_2.md). Earlier: [round one](TROUBLESHOOTING_ROUND_1.md).

Date: 2026-11-07. Status: **UNRELEASED — foundation checks pass; 3D user workflow acceptance is blocked.**

This is the first implementation slice, not a declaration that Primp is finished or market ready. No camera coaching, teaching, geometry sculpting, payments, or social feature is represented by a nonfunctional control. Those features have not been added to the product.

## Product intent

The original makeup-app conversation and summary establish real makeup teaching as the primary purpose, adapted to the learner's face, goals, and actual supplies. Phantom practice, manual painting, mask fallback, recording, challenges, and paid instructor interaction extend that purpose. The later avatar work adds surface painting and geometric contouring, with Primp operating independently and as an Avatar Foundry tool.

Original sources, preserved unchanged:

- [Design conversation](https://docs.google.com/document/d/1zuSzhiW6ZdkRMClkWPC4AvOX3ppZTDWlPaIwRKA-zKw/edit), archived as “makeeup app.”
- [Design summary](https://docs.google.com/document/d/1T7rvvZea88LswVCCO9izhUNGsbjZCpCFTd-ByneChV4/edit), archived with the working label “DALL Makeup.”
- Current owner direction: start with the makeup tools and digital avatar mirror; evaluate three solutions per major feature; keep experiments out of the released product; advance toward teaching, then evidence-based camera coaching.

The separate children's product stays separate. Adult Primp has no switch into a children's mode.

## Implemented code

- `static/primp.html`: responsive makeup workspace, local import/export, layer/tool controls, lighting controls, explicit failure states.
- `static/primp/app.mjs`: viewport, pointer interaction, UI state, bounded history, save/reopen, recovery scheduling, export.
- `static/primp/gltf-boundary.mjs`: bounded GLB metadata, graph, accessor, and image preflight.
- `static/primp/model.mjs`: GLB validation/loading boundary, paint targets, compositing, original texture/color handling, surface raycasts, resource disposal.
- `static/primp/core.mjs`: format limits, validation, interpolation, tile history, premultiplied-alpha blending.
- `static/primp/files.mjs` and `recovery.mjs`: confirmed-save boundary and transactional recovery revision checks.
- Counter program entry and Avatar Foundry link; existing profile, geometry, rig, and source assets are not replaced.

Tools are a hard pencil/lip brush, radial powder brush, alpha-aware local blending, and paint-layer erasing. Foundation, contour, blush, eyeshadow, eyeliner, and lips are independent editable layers with visibility and opacity. These are paint categories, not automatic anatomical segmentation. Color contour does not alter the mesh. The later Dremel must edit both underlying voxels and continuous cream together, with atomic undo; it is not implemented here.

Original material colors are baked into the underlying surface in linear light before returning to sRGB. Makeup is composited above that base, avoiding multiplication by the original skin tint. Original alpha and texture dimensions are retained. Normal, roughness, skeleton, morph, and animation structures remain attached; export is subject to the supported glTF exporter, not arbitrary extension-preserving byte identity. The .primp document retains the original GLB bytes exactly.

## Three-solution decisions and actual test coverage

“Considered” is not “executed.” Comparisons below must not be described as complete evaluation of every Primp feature.

| Major feature | Three approaches | Choice / evidence / remaining gate |
| --- | --- | --- |
| Surface attachment | UV texture painting; vertex color; projected decals | UV painting chosen for editable fine detail and existing skinning/morph attachment. Executed geometric detail/deformation assay and real Three.js raycast tests. A rendered decal comparison and expressive-avatar visual test remain open. |
| Brush/blend engine | Straight RGBA neighborhood average; browser blur filter; explicit premultiplied-alpha kernel | Executed transparent-edge comparison: naive red 24.4, kernel 220, browser filter 219 for input red 220. Chosen kernel has explicit bounded work and avoids transparent black fringes. Full viewport pointer/touch tests remain open. |
| Undo | Full image snapshots; replayed brush commands; exact touched-tile deltas | All three executed on ten edits. Snapshots: 80 MiB; tiles: 0.44 MiB. Tile undo/redo and cancellation restore identical pixels. Ten entries with a 64 MiB cap; unusually large edits can reduce retained depth. Timings in SESSION_ENDING_HANDOFF.md are fixture-specific. |
| Save and recovery | Flattened image; portable original-plus-layers document; browser database | All three exercised. PNG serves image export; .primp retains editable layers and original GLB; IndexedDB supplies transactional device recovery. Aborted write preserves previous record. The production UI save/reopen/restart sequence remains open. |
| Avatar import | GLB; glTF with separate files; FBX/OBJ conversion | Self-contained GLB chosen to avoid silent network dependencies and incomplete sidecars. Real existing rigged GLB loaded and exported/reimported. Conversion alternatives considered, not compared end to end; existing PubCast import tools remain the conversion path. |
| Mirror rendering | Existing local Three.js renderer; a separate custom WebGL engine; flattened 2D/photo mirror | Reuse existing pinned Three.js. No competing engine or flattened substitute. Context creation fails in this test browser; rendering, lighting quality, face framing, and GPU performance are NOT accepted. |
| Camera capture, later | Browser media capture; native capture; prerecorded clip review | Evaluate browser permissioned capture first while retaining manual/replay alternatives. No camera capture feature shipped. HTTPS/localhost, permission denial, iframe delegation, teardown, and offline model assets require acceptance. |
| Motion feedback, later | Explainable landmark kinematics; trained technique classifier; human-reviewed feedback | Start with independently validated speed/path cues and human guidance. No automated technique claims shipped. Compare all three on annotated clips and separate accuracy from detection confidence before selecting. |
| Teaching, later | Fixed video demonstration; interactive region-by-region overlay; guided exercises with explanation and feedback | Compare learning outcomes, not visual novelty. No unreviewed teaching library shipped. A lesson must explain the intended effect and how to adapt it, rather than simply ask the learner to copy a face. |
| Surface sculpting, later | Source voxel edits followed by cream regeneration; constrained edits of a continuous surface; mesh displacement | Compare against the audited filler engine before selecting. Preserve cream continuity, geometry, UVs, weights, and expressions; combine changes in a single undo transaction. Not implemented here. |

The production tree does not include the alternative-strategy test harness. Comparative assays live in `tests/primp/`.

## Teaching and inclusive rendering requirements

Teach proportion, balance, edges, contrast, texture, and the intended visual effect, with user-selected goals. An eyeliner shape can produce a different balance than intended; that is not a universal judgment that a person's face is wrong. Face geometry alone cannot determine a single correct aesthetic.

Evaluate across the full skin-tone range and undertones, including deep skin and very fair skin, with different lighting, exposure, makeup finishes, and camera behavior. Do not infer race from a camera frame or use race as a replacement for tone, undertone, features, and user goals. Include Black makeup artists and other relevant practitioners in lesson and rendering review. Treat washed-out highlights and lost shadow detail as measurable image-quality failures, not attributes to impose on every person in a group.

Each future lesson should record its goal, explanation, materials, substitutions, face-region guidance, application action (for example, dab versus sweep), lighting assumptions, demonstration, practice task, reviewer/source, and assessment limits. Source compilation and qualified review have not yet been performed; the empty library is not represented as a working feature.

Camera coaching must abstain when tracking is unreliable or occluded. Hand landmarks are not proof of pencil contact, brush pressure, product amount, or correctness. Stroke speed must be normalized against face scale and elapsed time, evaluated against the task, and calibrated on annotated clips before coaching language is enabled. No generic “perfect form” message from hand detection alone.

## Running

Use the existing authenticated PubCast host and open `/static/primp.html`, or open Primp from the Counter / Avatar Foundry. The page itself needs no new backend or package install. Save uses a native file picker where supported; download-only browsers retain the unsaved warning because download completion cannot be confirmed. Dependencies are the repository's local Three.js 0.160.0 modules and existing license/provenance files. Nothing downloads at application startup.

For isolated offline source inspection, serve the repository root with Python's built-in HTTP server and open the same path on localhost. This is not proof of authenticated host integration. Serving over file:// is unsupported because browser module loading requires an HTTP origin.

Focused checks: `node --test tests/primp/core.test.mjs`. The browser harness requires the real `tests/fixtures/avatars/mh_female.glb` served at `/fixtures/mh_female.glb`, the test HTML/module at `/qa/`, and the unchanged production modules at `/static/`. No test avatar is silently loaded into the product.

## Explicit limits and release gates

- WebGL is required; this environment cannot create a context. UI responds with an error and disables unavailable controls. There is no fake avatar image behind the error.
- The complete import → paint on a turning avatar → compare → save → reopen → export → restart flow has NOT been accepted in a functioning 3D viewport.
- Import preflight caps metadata at 4 MiB, nodes at 2,048 / depth 128, estimated decoded accessor storage at 64 MiB, and total decoded image pixels at 16 megapixels. Unsupported compact matrix layouts and animated WebP are explicitly refused. The legacy Manny/Sheila assets lack required buffer references and paint UVs; their preparation remains open.
- Source GLB: 30 MiB maximum; .primp file: 70 MiB maximum; up to four painted material surfaces. Paint layers are 1024 × 1024. Underlying skin texture dimensions are retained up to 4096 per dimension and within the explicit base/composite memory budget. Over-budget textures are rejected, never silently downsampled. Face-only/high-resolution makeup canvases require a future tested resolution policy.
- Paint follows the avatar's UV layout. Mirrored/overlapping UVs share paint; atlas distortion and island-edge bleed need explicit visual acceptance and improved edge isolation before a commercial release. The seam guard prevents long connecting lines but does not solve all island-edge cases.
- Material selection is manual. There is no automatic eye/lip/skin region classification, anatomical paint masking, or product finish simulation.
- Local recovery is scoped to this browser origin and device, uses one recovery slot, and is not a permanent backup or a separate authenticated per-person vault. Portable look files are the owner-controlled save path. Updated writers now refuse stale recovery writes in one transaction; mixed-version writers and account-scoped host integration remain open.
- Real phone/pen/touch performance, long-session memory, accessibility workflow, context restoration with an active model, and Windows acceptance remain open.
- No full PubCast regression or real authenticated host launch was run for this slice. Two existing focused Node regressions passed.
- No teaching, product database, camera access, Phantom gesture capture, coaching model, live classes, payment, or cloud sync implementation is claimed.
- The full three-solution program is incomplete. Only the explicitly recorded comparisons have executed evidence.
- No deployment, merge to main, release announcement, or production approval.

## Primary technical references checked

- [Khronos glTF specification](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc): linear material factors and sRGB texture handling.
- [Three.js GLTFExporter](https://threejs.org/docs/pages/GLTFExporter.html) and [Raycaster](https://threejs.org/docs/pages/Raycaster): current references checked; actual implementation uses the pinned local r160 source, not assumptions about the latest version.
- [Browser camera permissions and secure contexts](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).
- [MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker): landmarks/confidence inputs for later evaluation, not evidence of makeup technique recognition.
