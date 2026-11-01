# Visual Patch Approval Bridge Handoff

Date: 2026-06-11

## What Changed

Installed the first incorporation hook for the Visual Patch-Up Kit inside the
PubCast build. This connects approved visual patch/adaptive object proposals to
the existing PubWorld prop storage path and, when requested, the canonical
voxel-set storage path.

## New Files

- `modules/visual_patch_voxel_adapter.py`
  Converts Visual Patch Kit and adaptive prop proposals into PubWorld block
  payloads and voxel-set payloads.

- `modules/visual_patch_approval_bridge.py`
  Enforces approval/auto-approval and submits approved payloads through existing
  PubWorld/voxel storage functions.

- `tests/test_visual_patch_approval_bridge.py`
  Browser-free substitute for visual verification. It checks that an approved
  adaptive chair/tail-clearance patch persists as a PubWorld prop and a voxel
  set, and that an unapproved patch writes nothing.

## Updated File

- `main.py`
  Adds `POST /api/visual-patch/approve`.

## Endpoint Shape

`POST /api/visual-patch/approve`

Important fields:

- `approval.state`: must be `approved` or `auto_approved`
- `auto_approve`: optional boolean shortcut for supervised auto approval
- `patch_kind`: `visual_patch` or `adaptive_extension`
- `target`: `pubworld_prop`, `voxel_set`, or `both`
- `scene_id`: PubWorld scene id, defaults to `scene_default`

The endpoint refuses pending/unapproved requests before touching PubWorld or
voxel storage.

## Verification

The full pytest command could not start in this local environment because the
repo-level `tests/conftest.py` imports `starlette`, which is not installed in
the active Anaconda interpreter.

Substitute verification was run directly with Python and passed:

- approved adaptive tail-clearance chair patch saved as PubWorld prop
- same patch saved as canonical voxel set
- saved voxel set validates through `load_voxel_set`
- pending visual patch raises `VisualPatchApprovalError`
- pending visual patch creates no `pubworld` storage directory

## Notes

This is not the full live visual stage hookup. It is the approval-to-storage
bridge that makes the Visual Patch-Up Kit incorporable without requiring a
browser visual pass today.
