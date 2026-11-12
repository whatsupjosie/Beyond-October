# Primp gap closure — November 8, 2026

Status: implemented and tested authoring/data improvements on the existing work branch. Not commercially accepted; no merge or deployment.

## Delivered

- Brush output is clipped to the physically connected UV island. Blend input is isolated too, preventing color sampling from a nearby island. Interpolation retains the island identifier and resets on chart changes. Both cross-chart and folded same-chart overlapping UVs are refused. Unsupported/degenerate UV faces get an explicit error.
- Standard 1024 and fine 2048 paint detail, selected before preparing a surface. Fine paint survives compositing without reduction, portable format version 2, PNG decode, and reopening. Version 1 standard looks remain compatible. Paint layers plus atlas masks are bounded at 128 MiB; original texture/base/composite, imported image, project, and undo budgets remain separate. This does not claim a 128 MiB total process footprint.
- Prepared Manny and Sheila buttons use derived, self-contained GLBs. Source assets are untouched. `PROVENANCE.json` records hashes and tool version. Triangle order, positions, normals, joints, weights, nodes, skins, animations, original material factors and emission are preserved. Original vertex colors are baked into sRGB textures so paint is not multiplied by those colors again. Each original contains 34 collapsed pole triangles; they remain preserved and are not treated as visible paint area. These bases still have their original simple anatomy, not newly authored expressive facial detail.
- Recovery uses separate verified-account databases on auth-enforced PubCast hosts. It rechecks the session before recovery actions; account changes, unverifiable sessions, and host errors pause recovery. Standalone storage remains independent. Existing unowned standalone records are never automatically assigned to an account. This separates normal account workflows, not malicious same-origin script access or device ownership.
- Revisioned recovery migrates on the first successful new write to a new key. A legacy tab can still change its legacy record but cannot overwrite the new record. Concurrent/stale writes and clone failures preserve the committed winner.
- Cutout picking samples the actual base texture alpha and alpha-map green channel, including their texture transforms. It uses a one-pixel sampling canvas rather than duplicating an entire texture. Unsupported texture channels remain occluders.
- The shared Reach authentication adapter is reused. The real PubCast application starts and serves Primp modules, source assets, and prepared avatars. Real password login, verified session, invalid token refusal, logout, and a second lifespan entry passed.

## Verification

Executed against the final code:

```sh
node --test tests/primp/*.test.mjs tests/test_voxel_block_preview_client_node.js tests/test_foresight_file_close_node.js
```

36 passed, zero failed. Includes source-byte/provenance integrity, strict derived GLB import, exact triangle attribute preservation, nonoverlapping 2048 atlases, island rasterization, high-detail schema, interpolation, memory refusal, session scope decisions, history, save adapter, and existing focused regressions.

```sh
python -m pytest tests/test_primp_host_integration.py tests/test_websocket_cookie_auth.py tests/test_three_solution_rounds_auth_foundation.py tests/test_full_host_route_authority.py -q
```

13 passed. Used installed canonical requirements plus pytest, scratch runtime data, enforced auth, and an ephemeral generated test JWT secret. Two runner warnings: deprecated AnyIO alias in Starlette, and absent pytest-asyncio plugin/config support. These tests are synchronous and passed; no asynchronous suite coverage is inferred. Host test uses an isolated subprocess and actual lifespan/login/static routes, not a substituted API. Existing optional speech/vision integrations report unavailable dependencies; those integrations were not accepted by this test.

Browser harness (`tests/primp/browser.html` and `browser.mjs`): **23 passed, zero failed** using real browser Canvas, IndexedDB connections, Three.js loader/exporter/raycasts, prepared asset decoding, 2048 project round trip, and nearby-island brush/blend isolation. The unchanged pinned local Three.js modules are used. Test copies are served only in the QA preview; no QA fixture is loaded into the product automatically.

## Defects caught while implementing this continuation

- Interpolated points initially lost the new island identifier; fixed and regression tested.
- A fine layer could initially be reduced by a lower-resolution composite; fixed with separate original-base and composite dimensions/budget, then browser tested.
- New prepared assets exposed 34 pre-existing collapsed faces per base; geometric analysis confirmed zero visible area. Tests explicitly require every refused prepared face to be physically degenerate, rather than ignoring arbitrary UV failures.
- The old schema test deliberately rejected version 2. Updated it to reject unsupported version 3 and added explicit valid/invalid high-detail format cases.
- Session status initially accepted malformed false-like host status; now requires explicit boolean status and fails closed on malformed host responses.

## Build and asset preparation

`tools/prepare_primp_bases.py` requires build-time xatlas 0.0.11, NumPy, and Pillow. Tool provenance: https://github.com/mworchel/xatlas-python/tree/v0.0.11 (MIT). It runs only when deliberately rebuilding the checked-in derived files. Primp performs no startup package installation or asset conversion. Original input hashes and derived output hashes are recorded in `static/primp/avatars/PROVENANCE.json`. Original assets remain under `assets/avatar/`.

## Remaining acceptance and capability boundaries

- The cloud browser again reports **Error creating WebGL context**. The real product correctly disables graphics controls and shows the error. Rendered mirror appearance, interactive 3D painting/turning, before/after, lighting, rendered export appearance, and the complete UI save/reopen/restart sequence cannot be signed off here. Data/Canvas tests do not replace this gate.
- Actual phone, touch/pen, Windows, accessibility workflow, GPU recovery, long-session memory, expressive-avatar UV distortion/seam appearance, and performance acceptance remain open. Preparation is synchronous and bounded; the triangle/work limits are resource guards, not measured responsiveness guarantees.
- Anatomical classification, advanced product finish simulation, generalized imported vertex-color compensation, and higher UV-channel/vertex-alpha cutout picking remain outside accepted behavior. Standard texture alpha-test and fully transparent texels no longer block paint picking; semitransparent visible surfaces still occlude. Live vertex-colored paint targets are explicitly refused to prevent silent tinting. Prepared Manny/Sheila vertex color handling is explicitly covered.
- Cream/voxel Dremel, mesh baking integration, teaching content, permissioned camera capture, and technique coaching remain separate work. No placeholder controls or experimental coaching were added. Continuous cream and joint atomic geometry undo remain required for that later sculpting integration.
- Three-solution comparisons remain partial. `BUILD_AND_ACCEPTANCE.md` distinguishes considered options, executed comparisons, and unfulfilled acceptance criteria.

The work remains on `gpt/primp-canvas-preparation-2026-11-07`. No main merge, deployment, GitHub Action, or release claim.
