from __future__ import annotations

import json

import pytest

from modules.pubworld_blocks import create_prop
from modules.visual_patch_approval_bridge import VisualPatchApprovalError, submit_approved_visual_patch
from modules.voxel_set_contract import load_voxel_set, save_voxel_set


def _stage_voxels(blocks):
    return [[int(block["x"]), int(block["y"]), int(block["z"])] for block in blocks]


def test_approved_adaptive_extension_saves_pubworld_prop_and_voxel_set(tmp_path):
    result = submit_approved_visual_patch(
        tmp_path,
        {
            "patch_kind": "adaptive_extension",
            "target": "both",
            "scene_id": "scene_default",
            "asset_id": "minotaur_tail_chair_patch",
            "approval": {"state": "approved"},
            "adaptive_extension": {
                "extension_id": "tail_chair_patch",
                "object_id": "chair_01",
                "object_type": "chair",
                "interaction": "sit",
                "reason": "make chair usable for avatar silhouette and tail clearance",
                "voxel_patch": {
                    "dimensions": [8, 5, 5],
                    "subtractive_cutouts": [{"operation": "subtract", "kind": "tail_slot"}],
                },
            },
        },
        create_prop_func=create_prop,
        save_voxel_set_func=save_voxel_set,
        stage_voxels_func=_stage_voxels,
    )

    assert result["ok"] is True
    assert result["patch_kind"] == "adaptive_extension"
    assert result["prop"]["scene_id"] == "scene_default"
    assert result["voxels"]
    assert result["voxel_set_path"]

    voxel_set = load_voxel_set(result["voxel_set_path"])
    assert voxel_set["asset_id"] == "minotaur_tail_chair_patch"
    assert voxel_set["safety"]["approved_by_user"] is True

    prop_files = list((tmp_path / "pubworld" / "props").glob("*.json"))
    assert len(prop_files) == 1
    saved_prop = json.loads(prop_files[0].read_text(encoding="utf-8"))
    assert saved_prop["variants"][0]["subtractive_cutouts"][0]["kind"] == "tail_slot"


def test_unapproved_patch_is_rejected_before_storage(tmp_path):
    with pytest.raises(VisualPatchApprovalError):
        submit_approved_visual_patch(
            tmp_path,
            {
                "patch_kind": "visual_patch",
                "target": "pubworld_prop",
                "approval": {"state": "pending"},
                "patch": {"patch_id": "pending_patch", "dimensions": [2, 2, 1]},
            },
            create_prop_func=create_prop,
            save_voxel_set_func=save_voxel_set,
            stage_voxels_func=_stage_voxels,
        )

    assert not (tmp_path / "pubworld").exists()
