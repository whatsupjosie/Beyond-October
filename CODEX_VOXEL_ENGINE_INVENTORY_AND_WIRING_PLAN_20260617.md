# PubCast Voxel Engine Inventory And Wiring Plan

Date: 2026-06-17
Scope: Big Zip construction copy plus user-referenced voxel source archives. Non-destructive inventory only; no engine merge performed in this pass.

## Required First Read

Before continuing this work, read:

`C:\Users\hardc\Downloads\CODEX_PUBCAST_AUTONOMOUS_SPINE (2).md`

The spine rules matter here because voxel systems touch runtime authority, avatar/object interaction, rendering, and recovery status.

## Current Big Zip Voxel Foundation

Active construction build:

`C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614`

Currently installed/tested voxel files:

```text
modules/voxel_set_contract.py
modules/voxel_block_kit.py
tests/test_voxel_set_contract.py
tests/test_pubblock_voxel_block_kit.py
CODEX_PUBBLOCK_VOXEL_KIT_HANDOFF.md
```

Verified test command:

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py -q
```

Result:

```text
8 passed in 0.38s
```

## What Is Ready Right Now

### PubBlock Measurement Contract

`modules/voxel_set_contract.py` defines the base measurement rules:

```text
1 full PubBlock = 10 inches = 0.254 meters
half block = 5 inches
quarter block = 2.5 inches
coordinates are integer subdivision units
unit_profile = pub_block_10in
```

This is already tested and should be treated as the canonical construction measurement basis for PubWorld.

### PubBlock Voxel Block Kit

`modules/voxel_block_kit.py` provides tested builder helpers:

```text
block
rectangular_prism
stage_floor
flat_wall
backdrop_panel
guide_grid
doorway_wall
make_voxel_set
```

Important behavior:

- Stage floors validate through the canonical voxel set contract.
- Guide grid blocks are hidden from program/filming output.
- Backdrop panels support image IDs.
- Doorway wall pieces support simple stage/set construction.
- Blocks are normalized through `normalize_voxel_set`.

This is ready for UI/status wiring, but it is not yet a full visual editor.

## User-Referenced Candidate Sources

### `podcast_ai_voxel_engine_COMPLETE.zip`

Contains heavier voxel engine source and docs:

```text
HANDOFF.md
SYSTEM_ANALYSIS.md
IMPLEMENTATION_GUIDE.md
IMPLEMENTATION_COMPLETE.md
voxel_renderer.py
engine.rs
character_engine.py
lighting_engine.py
distributed_engine.py
distributed_engine_node_trio_ready_apr12_2026.py
Enhanced_control_room_HTML_integration_-_Claude.html
```

Assessment:

- Useful candidate/reference archive.
- Do not merge directly without comparing contracts and dependencies.
- Likely contains renderer/distributed engine ideas that may be valuable later.

### `podcast_ai_voxel_engine_handoff.zip`

Similar to the complete zip, mostly handoff/docs plus engine pieces.

Assessment:

- Good comparison/reference archive.
- Likely overlaps heavily with `podcast_ai_voxel_engine_COMPLETE.zip`.

### `podcast_engine_voxel_integration.zip`

Contains integration-oriented source:

```text
code_collector_spec/character_engine.py
code_collector_spec/test_integration.py
code_collector_spec/MEMORY_LAYER_SPEC.md
code_collector_spec/engine_patch.py
code_collector_spec/distributed_engine_node_real.py
code_collector_spec/voxel_renderer.py
code_collector_spec/prosody_engine.py
code_collector_spec/lighting_engine.py
code_collector_spec/config.yaml
```

Assessment:

- More integration-focused than the simple handoff zips.
- Candidate for future comparison against Big Zip modules.
- Do not wire until dependencies, event contracts, and data model are checked.

### `pubcast_motion_voxel_systems_v1 (1) - Copy.zip`

Contains both motion and voxel consolidation material:

```text
consolidation/avatar_motion/pubcast_motion_runtime_integration.zip
consolidation/avatar_motion/pubcast_glb_motion_consumer_bridge.zip
consolidation/avatar_motion/pubcast_behavior_animation_system.zip
consolidation/avatar_motion/MANNY_SHEILA_CAMERA_AUDIT_V1_051326_0345am.md
consolidation/voxel_builder/pubworld_blocks.py
consolidation/voxel_builder/pubcast_voxel_hollow_patch.py
consolidation/voxel_builder/voxel-kit-1_0.zip
consolidation/voxel_builder/voxel_llm_adapter.py
consolidation/voxel_builder/podcast_ai_voxel_engine_COMPLETE.zip
consolidation/voxel_builder/pubworld_blocks__1_.py
consolidation/voxel_builder/pubworld_voxel_primitives_v1.zip
```

Assessment:

- High-value consolidation bundle.
- It bridges motion/avatar and voxel-builder work.
- Best next candidate for deeper comparison, especially `pubworld_blocks.py`, `pubcast_voxel_hollow_patch.py`, and nested motion bridge zips.

### `pubworld_voxel_primitives_v1.zip`

Contains small GLB primitive assets:

```text
cube_0p25.glb
cube_0p5.glb
cube_1p0.glb
wedge_0p25.glb
wedge_0p5.glb
wedge_1p0.glb
corner_inner_0p25.glb
corner_inner_0p5.glb
corner_inner_1p0.glb
corner_outer_0p25.glb
corner_outer_0p5.glb
corner_outer_1p0.glb
```

Assessment:

- This maps well to the quarter/half/full PubBlock rule.
- Candidate for asset-library import/copied reference, not direct code wiring.
- Needs a manifest before use in the build.

### `pubcast_voxel_hollow_patch.py`

This is a patch script that modifies voxel contract and main route helpers to understand:

```text
hollow culling
face culling
greedy meshing
exposed_faces
hollow flag
interior voxel skip
```

Assessment:

- Important conceptually, but it is a patch script aimed at older code shapes.
- Do not run it directly on the current construction build.
- Safer path: extract its data-contract ideas into targeted tests and small manual edits later.

### `voxel.wgsl`

Simple WGSL shader:

```text
camera uniform
position/color vertex input
basic color fragment output
```

Assessment:

- Useful as minimal renderer reference.
- Not enough by itself for PubWorld rendering features.
- Could be a baseline shader for a WebGPU renderer later.

### Visual Patch Kit Copy Bundle

Referenced manifest:

`C:\Users\hardc\Downloads\big zip\visual_patch_kit_for_big_zip_20260611_20260611_172957\visual_patch_kit_for_big_zip_20260611\VISUAL_PATCH_KIT_COPY_MANIFEST.md`

Key copied systems:

```text
runtime/spine/visual/voxel_patch_adapter.py
runtime/spine/visual/patch_workflow.py
runtime/spine/visual/styling_aide.py
runtime/spine/performers/visual_patch.py
runtime/spine/performers/interaction_fit.py
runtime/spine/performers/contact.py
runtime/spine/performers/motion_feedback.py
```

Assessment:

- This is the future bridge between avatar/object fitting problems and voxel patch generation.
- It is explicitly copy-only/unhooked right now.
- Should be wired only after Pub Manager/status visibility and voxel contract readiness are firm.

## Image Reference

`C:\Users\hardc\Downloads\voxel_kit_preview.png`

The preview shows a clean grid of simple white cube voxel primitives. This fits the PubBlock idea visually: simple blocks first, then fine subdivisions and asset-library primitives later.

## Recommended Wiring Order

### Pass 1: Status-Only Voxel Readiness Wiring

Goal: make voxel health visible without changing rendering behavior.

Suggested work:

1. Add `/api/voxel/block-kit/status` or expand existing voxel status if already present.
2. Report PubBlock constants, subdivision support, available builder helpers, and test status assumptions.
3. Add Pub Manager raw status entry for `voxel_block_kit`.
4. Add menu coverage under Scene/Room or Visual Patch Kit for `voxel_block_kit_status`.
5. Add tests that call the route and assert the constants are correct.

### Pass 2: Primitive Asset Manifest

Goal: make `pubworld_voxel_primitives_v1.zip` usable without dumping loose GLBs into the build blindly.

Suggested work:

1. Create a manifest format for primitive assets.
2. Copy/extract primitives into a clearly labeled copied asset folder only after user approval or into construction copy only.
3. Include sizes: 0.25, 0.5, 1.0 block.
4. Map primitive names to PubBlock subdivisions.
5. Add tests for manifest parsing.

### Pass 3: Hollow/Face-Culling Contract

Goal: adopt hollow-culling safely.

Suggested work:

1. Add `exposed_faces` as optional block metadata or a top-level supported field only after contract tests are written.
2. Add tests proving `exposed_faces=[]` is treated as an interior voxel and skipped by converters.
3. Do not run the old patch script directly.
4. Fold the concept into current `voxel_set_contract.py` with small reversible edits.

### Pass 4: Visual Patch Adapter Bridge

Goal: connect visual patch requests to voxel payload proposals.

Suggested work:

1. Keep approval gates intact.
2. Add event-bus messages for patch proposal/request/approval.
3. Let Pub Manager report pending patch proposals.
4. Keep permanent save actions approval-required.
5. Add tests for temporary patch, cache expiry, save-to-inventory, and room persistence decisions.

### Pass 5: Renderer Integration

Goal: renderer/runtime integration after contracts are solid.

Suggested work:

1. Compare `voxel_renderer.py`, Rust `engine.rs`, and WGSL shader references.
2. Decide renderer target: Python tool, Rust service, browser/WebGPU, or Three.js fallback.
3. Add minimal status route first.
4. Only then wire live rendering.

## Hard No For Now

- Do not run `pubcast_voxel_hollow_patch.py` directly against the construction build.
- Do not delete or overwrite current Big Zip voxel files.
- Do not wire Visual Patch Kit permanent-save behavior without approval gates.
- Do not merge renderer/distributed engine archives without comparing dependencies and contracts.

## Best Immediate Next Step

The safest next implementation pass is:

```text
Add a read-only voxel block kit status endpoint plus Pub Manager/menu coverage for voxel block kit readiness.
```

Why:

- The module is already installed.
- The tests already pass.
- It gives the player/director/Pub Manager visibility.
- It does not alter rendering, asset storage, or WebSocket contracts.

## Verification Baseline

Keep this green while continuing:

```powershell
& 'C:\Users\hardc\anaconda3\python.exe' -m pytest -p no:cacheprovider tests\test_voxel_set_contract.py tests\test_pubblock_voxel_block_kit.py -q
```

Expected:

```text
8 passed
```