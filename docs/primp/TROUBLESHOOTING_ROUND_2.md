# Primp deep polish and troubleshooting round two

Date: 2026-11-07 (Los Angeles). Starting remote source: `2f3fce009ab7be010c1d495be1da8c547265c89f`; matching local tree `be1e6dfe35d91a6dd230e19fdee76ddce6714f02`.

**Status: UNRELEASED. This pass hardens the existing implementation; it does not establish that the 3D makeup experience is ready.**

## Findings and fixes

1. **The previous undo-memory repair did not actually release all the excluded buffers.** Finalization excluded unchanged tiles from its returned byte count but retained them in the TileEdit map, which remained reachable through command callbacks. A focused test reproduced nine retained tiles while the command charged for one. The map now discards unchanged entries. Both the retained map and command size are checked; real Canvas undo/redo still restores identical pixels. This removes the known retaining references; it is not a measured physical-device heap/GC proof.

2. **The GLB boundary trusted decoded resource declarations.** Before changing it, five focused regression cases failed: truncated binary chunks, cyclic/deep nodes, enormous accessor allocations in a tiny file, oversized image dimensions, and retained undo buffers. Inspecting the pinned Three.js loader confirmed it can allocate arrays directly from accessor counts. The importer now checks complete chunk lengths/order, asset version, binary buffer/view bounds, node topology/depth, metadata nesting, sparse index order/range, decoded geometry limits, image dimensions, and aggregate decoded image pixels before invoking the loader. Required unsupported extensions and remote resources remain refused. This is a bounded importer, not a complete glTF conformance validator or a guarantee that native decoders cannot fail.

3. **Texture preparation could leave half-committed state.** The old path assigned target.base and replaced the material before all preparation/notification work succeeded. Preparation now composes a staged surface, commits it together, and restores the old map/color and releases staged texture/canvas references if an error occurs. Actual browser failure injection confirms rollback and a successful retry.

4. **Explicit UV texture matrices were overwritten.** The hit path always recalculated the matrix and the new paint texture failed to preserve manual matrix mode. Hit testing now honors matrixAutoUpdate, and prepared textures copy the original mode and matrix. A real Three.js raycast test verifies the before/after coordinates match for an explicit matrix.

5. **Invisible materials still blocked surface selection.** Object visibility was checked, but material visibility was not. Invisible materials are now skipped by the hit-selection boundary. A real raycast fixture verifies the surface behind an invisible material remains selectable. Alpha-cutout texture holes are a separate unresolved visual issue.

6. **Brush errors could leak Canvas state.** Brush drawing now restores its saved context in finally, including when pixel reads or drawing fail. The rendered pointer/error workflow remains unverified; this guard has source review and syntax evidence, not a full UI failure injection.

7. **Recovery and portable files did not share an aggregate size boundary.** The UI's final portable-file Blob check did not bound the recovery snapshot builder. A common canonical-document byte counter now includes UTF-8 names, original-source base64, metadata, and every layer. Building a snapshot stops at the limit before creating the remaining layer strings. Imported documents use the same check. Failed size checks leave open paint and the previous recovery record intact. Node checks compare the counter with actual UTF-8 JSON bytes, including a non-ASCII name; the browser checks a real editable look.

8. **A stale recovery failure could report against the new document.** Asynchronous recovery failures now check the document generation before replacing its current storage message. This path is reviewed and syntax checked; a complete interactive document-switch race test is still open.

## Import limits and compatibility

The importer deliberately bounds metadata to 4 MiB, 2,048 nodes, depth 128, 64 MiB estimated decoded accessor storage, 4,096 pixels per image side, and 16 megapixels across encoded images. Source GLB and portable look limits remain 30 MiB and 70 MiB. These are conservative implementation limits, not hardware-performance claims. More complex assets receive explicit errors rather than silent texture reduction. Padded compact matrix accessors unsupported by this pinned importer and animated WebP textures are rejected explicitly.

A scan of nine bundled GLB files accepted seven files, including duplicate fixture copies. It rejected the two legacy `assets/avatar/manny.glb` and `sheila.glb`: their buffer views omit the required buffer index, and their mesh attributes contain no paint UV coordinates. Their original bytes are untouched. This is a discovered asset limitation, not a claim that seven different avatars passed a rendered workflow. No compatibility workaround silently invents buffer references or UVs. Preparing these legacy assets for paint remains open.

Real browser-encoded PNG, JPEG, and WebP headers are checked for correct dimensions. Header inspection bounds allocation; actual image decoding still performs format validation and can reject malformed payloads.

## Verification ledger

- Baseline negative run: five new focused tests failed before corrections, with explicit missing-rejection failures and a nine-versus-one tile retention mismatch.
- Final Node command: `node --test tests/primp/*.test.mjs tests/test_voxel_block_preview_client_node.js tests/test_foresight_file_close_node.js` — 27 passed, zero failed, including two existing focused regressions.
- Final actual-browser result: 18 passed, zero failed. Includes real PNG/JPEG/WebP dimension reading, staged preparation rollback/retry, explicit UV matrix preservation, invisible-material selection, editable-file size counting, real IndexedDB conflicts, and GLB/paint/rig round trips. These are data/Canvas/raycast checks, not a functioning 3D viewport.
- Syntax checks: changed application, core, model, importer, and browser test modules passed.
- Actual existing rigged avatar import/export/reimport checks preserve the fixture's 52 bones, one animation, paint, and a deliberately added morph target. This establishes the tested data round trip, not rendered visual quality.
- The cloud browser screenshot attempt timed out. No image proof is claimed.
- No full authenticated host, Windows, physical phone, long-session heap/GPU, or native file-picker acceptance was run. The earlier inability to create WebGL still blocks the full viewport acceptance gate.

## Remaining release gates

Complete the rendered avatar paint/turn/compare/save/reopen workflow; UV-island edge isolation and overlapping layouts; high-detail makeup resolution; visual alpha-cutout hit testing; unsupported glTF extension fidelity; per-account recovery and mixed-version writer behavior; legacy base-avatar preparation; full host/device/accessibility/soak acceptance. Camera coaching and teaching are still separate future work. No deployment, main merge, or release approval.

The stricter import boundary compares three choices: trusting the loader, repairing/guessing malformed data, and validating bounded supported input first. Chosen: bounded validation with explicit refusals and preserved original bytes. Staged texture preparation compares mutating in place, cloning the full avatar for every preparation, and staging only the new surface. Chosen: surface staging with rollback, verified by failure injection. Undo continues to use exact pixel tiles; this pass repairs its retention rather than replacing its tested representation.

Primary references checked: [Khronos glTF 2 specification](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc), [WebP container specification](https://developers.google.com/speed/webp/docs/riff_container), and the repository's pinned Three.js r160 GLTFLoader source.
