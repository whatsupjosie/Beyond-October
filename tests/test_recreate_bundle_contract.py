import json

from modules.recreate_bundle import AvatarRigRef, RecreateBundle, TimedEvent, blank_bundle


def test_blank_bundle_contains_required_pubcast_recreate_fields():
    bundle = blank_bundle(
        session_id="s1",
        project_id="p1",
        scene_id="studio",
        take_id="take-001",
    )
    bundle.final_program_ref = "exports/s1/program.mp4"
    bundle.stage_environment_version = "studio-v6"
    bundle.avatars.append(
        AvatarRigRef(
            avatar_id="manny",
            display_name="Manny",
            asset_uri="/assets/avatar/manny.glb",
            rig_version="unknown",
            skeleton_version="pubcast-standard",
            animation_status="no embedded animations found",
        )
    )
    bundle.add_camera_event("cut", **{"from": "wide_shot", "to_camera": "medium_shot"})
    bundle.mocap_events.append(TimedEvent("mocap_unavailable", payload={"source": "status"}))
    bundle.audio_refs.append({"track_id": "program_mix", "status": "metadata_only"})
    data = bundle.to_dict()
    assert data["session_id"] == "s1"
    assert data["project_id"] == "p1"
    assert data["scene_id"] == "studio"
    assert data["take_id"] == "take-001"
    assert data["final_program_ref"] == "exports/s1/program.mp4"
    assert data["camera_timeline"][0]["event_type"] == "cut"
    assert data["camera_timeline"][0]["payload"]["source"] == "director_switcher"
    assert data["avatars"][0]["asset_uri"].endswith("manny.glb")
    assert data["avatars"][0]["asset_type"] == "glb"
    assert data["avatars"][0]["performer_asset"] is True
    assert data["avatars"][0]["sprite_replacement_allowed"] is False
    assert "system_warnings" in data


def test_recreate_bundle_round_trips_json_without_losing_required_fields():
    bundle = blank_bundle(session_id="s2", project_id="p2", scene_id="studio", take_id="take-002")
    bundle.final_program_ref = "exports/s2/program.mp4"
    bundle.stage_environment_version = "studio-v6"
    bundle.add_camera_event("preview", to_camera="wide_shot")
    bundle.mocap_events.append(TimedEvent("mocap_reference", payload={"stream": "unavailable"}))
    bundle.avatars.append(
        AvatarRigRef(
            avatar_id="sheila",
            display_name="Sheila",
            asset_uri="/assets/avatar/sheila.glb",
            rig_version="unknown",
            skeleton_version="skin-present-pending-retarget-map",
        )
    )
    bundle.audio_refs.append({"track_id": "program_mix", "status": "metadata_only"})
    bundle.update_readiness()
    reloaded = RecreateBundle.from_dict(json.loads(bundle.to_json()))
    assert reloaded.session_id == "s2"
    assert reloaded.avatars[0].avatar_id == "sheila"
    assert reloaded.camera_timeline[0].payload["to_camera"] == "wide_shot"
    assert reloaded.recreate_readiness == "ready"


def test_recreate_bundle_explains_not_ready_reasons():
    bundle = blank_bundle(session_id="s3", project_id="p3", scene_id="studio", take_id="take-003")
    readiness = bundle.update_readiness()
    assert readiness.startswith("not_ready:")
    assert "missing final program" in readiness
    assert "missing camera timeline" in readiness
