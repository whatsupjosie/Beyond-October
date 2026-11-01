from modules.pub_manager_recovery import build_snapshot, issue_report, suggest_recovery, validate_action


def test_validate_action_separates_safe_from_approval_required():
    safe = validate_action("program_audio.stop_all")
    assert safe["ok"] is True
    assert safe["requires_approval"] is False
    risky = validate_action("files.delete")
    assert risky["ok"] is False
    assert risky["requires_approval"] is True


def test_snapshot_rolls_up_severity():
    snap = build_snapshot({"audio": {"error": "loop detected"}})
    assert snap.overall() == "error"
    systems = {item["system"]: item for item in snap.to_dict()["systems"]}
    assert systems["audio"]["severity"] == "error"


def test_suggest_recovery_for_audio_and_motion():
    snap = build_snapshot({"audio": {"error": "loop"}, "motion": {"warning": "pose drift"}})
    ids = {item["action_id"] for item in suggest_recovery(snap)}
    assert "program_audio.stop_all" in ids
    assert "animation.stop_all" in ids
    assert "avatar.reset_pose" in ids


def test_issue_report_contains_suggestions_and_errors():
    snap = build_snapshot({"assets": {"warning": "missing background"}})
    report = issue_report(snap, recent_errors=["404 background.png"])
    assert report["overall"] == "warn"
    assert report["recent_errors"] == ["404 background.png"]
    assert report["suggestions"]


def test_voxel_block_kit_status_is_safe_and_suggested_when_warned():
    safe = validate_action("voxel.block_kit_status")
    assert safe["ok"] is True
    assert safe["requires_approval"] is False
    snap = build_snapshot({"voxel_block_kit": {"warning": "missing block kit"}})
    ids = {item["action_id"] for item in suggest_recovery(snap)}
    assert "voxel.block_kit_status" in ids
    preview = validate_action("voxel.block_kit_preview")
    assert preview["ok"] is True
    assert preview["requires_approval"] is False