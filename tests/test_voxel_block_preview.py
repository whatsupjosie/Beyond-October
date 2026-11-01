from modules.voxel_block_preview import VoxelBlockPreviewError, preview_capabilities, preview_voxel_asset


def test_pubblock_stage_floor_preview_is_read_only_and_measured():
    preview = preview_voxel_asset("stage_floor", {"width": 3, "depth": 2, "subdivision": 4})

    assert preview["ok"] is True
    assert preview["read_only"] is True
    assert preview["saved"] is False
    assert preview["creates_map_rooms"] is False
    assert preview["creates_consoles"] is False
    assert preview["measurement"]["base_block_inches"] == 10
    assert preview["measurement"]["subdivision"] == 4
    assert preview["measurement"]["unit_inches"] == 2.5
    assert preview["block_count"] == 96
    assert preview["voxel_set"]["safety"]["approved_by_user"] is False


def test_adaptive_extension_preview_keeps_tail_slot_without_persistence():
    preview = preview_voxel_asset(
        "adaptive_extension",
        {
            "asset_id": "minotaur_tail_chair_preview",
            "adaptive_extension": {
                "extension_id": "tail_chair_patch_preview",
                "object_id": "chair_01",
                "object_type": "chair",
                "interaction": "sit",
                "voxel_patch": {
                    "dimensions": [8, 5, 5],
                    "subtractive_cutouts": [{"operation": "subtract", "kind": "tail_slot"}],
                },
            },
        },
    )

    assert preview["preview_kind"] == "adaptive_extension"
    assert preview["saved"] is False
    assert preview["block_count"] > 0
    assert preview["voxel_set"]["asset_id"] == "minotaur_tail_chair_preview"
    assert preview["voxel_set"]["safety"]["approved_by_user"] is False
    assert preview["voxel_set"]["safety"]["sandbox_only"] is True


def test_preview_capabilities_are_explicitly_non_mutating():
    caps = preview_capabilities()

    assert caps["available"] is True
    assert caps["read_only"] is True
    assert caps["saves_assets"] is False
    assert "adaptive_extension" in caps["supported_previews"]
    assert "stage_floor" in caps["supported_previews"]


def test_preview_rejects_unsupported_kind():
    try:
        preview_voxel_asset("map_room", {})
    except VoxelBlockPreviewError as exc:
        assert "preview_kind" in str(exc)
    else:
        raise AssertionError("unsupported preview kind should fail")