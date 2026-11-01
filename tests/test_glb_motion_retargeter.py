from modules.glb_motion_retargeter import canonical_bone, clamp_rotation, normalize_payload


def test_clamps_rotations_and_preserves_zero():
    assert clamp_rotation([90, 0, -90], max_degrees=35) == [35, 0.0, -35]


def test_aliases_manny_sheila_bones_to_canonical():
    assert canonical_bone("Pelvis") == "hips"
    assert canonical_bone("Spine_01") == "spine"
    assert canonical_bone("UpperArm_L") == "left_arm"


def test_normalize_payload_drops_unknown_bones_and_bad_kinds():
    payload = {
        "avatar_id": "manny",
        "commands": [
            {"kind": "mocap_pose", "weight": 2, "pose": {"bones": {
                "Head": {"rotation": [10, 0, 99]},
                "NotARealBone": {"rotation": [5, 5, 5]},
            }}},
            {"kind": "unsafe", "pose": {"bones": {"Head": {"rotation": [1, 2, 3]}}}},
        ],
    }
    out = normalize_payload(payload)
    assert out["avatar_id"] == "manny"
    assert len(out["commands"]) == 1
    cmd = out["commands"][0]
    assert cmd["weight"] == 1.0
    assert cmd["pose"]["bones"] == {"head": {"rotation": [10.0, 0.0, 35.0]}}


def test_empty_or_malformed_payload_is_safe():
    assert normalize_payload({"avatar_id": "x", "commands": [{"pose": {"bones": []}}]}) == {"avatar_id": "x", "commands": []}
