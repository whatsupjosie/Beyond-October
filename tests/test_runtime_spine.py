from runtime.spine import EventBus, PerformerRegistry, RuntimeState
from runtime.spine.performers import AnimationAuthority, LocomotionSystem, build_replication_snapshot
from runtime.spine.stations import CameraStation


def test_event_bus_emits_immutable_event_and_unsubscribes():
    bus = EventBus()
    seen = []
    token = bus.subscribe("pub:message", seen.append)
    event = bus.emit("pub:message", {"text": "hi"}, source="test")
    assert seen[0]["data"]["text"] == "hi"
    try:
        event["source"] = "bad"
        assert False
    except TypeError:
        pass
    bus.unsubscribe(token)
    bus.emit("pub:message", {"text": "again"}, source="test")
    assert len(seen) == 1


def test_performer_registry_locomotion_and_replication():
    bus = EventBus()
    registry = PerformerRegistry(bus)
    performer = registry.spawn_performer("p1", "Manny", [0, 0, 0], "studio")
    locomotion = LocomotionSystem(registry, bus, speed=10.0)
    locomotion.move_to("p1", [1, 0, 0])
    locomotion.update(0.2)
    assert performer.position[0] > 0
    assert performer.skeleton_pose["animation"] == "walk"
    snap = build_replication_snapshot([performer], dirty_only=True, mark_clean=True)
    assert snap["count"] == 1
    assert performer.dirty is False


def test_station_registry_and_runtime_state_snapshot():
    state = RuntimeState()
    state.performers.spawn_performer("p1", "Sheila", [0, 0, 0], "studio")
    camera = CameraStation("cam_a", state.event_bus)
    state.stations.register_station(camera)
    assert state.stations.activate_station("cam_a", "p1") is True
    camera.on_interaction("p1", {"live": True, "target": "p1"})
    snap = state.snapshot()
    assert snap["stations"]["cam_a"]["live"] is True


def test_animation_authority_uses_highest_priority_bone_first():
    authority = AnimationAuthority()
    authority.submit("p1", "base", {"bones": {"head": {"rotation": [1, 0, 0]}}}, priority=10)
    authority.submit("p1", "overlay", {"bones": {"head": {"rotation": [5, 0, 0]}, "spine": {"rotation": [0, 1, 0]}}}, priority=50)
    pose = authority.resolve("p1")
    assert pose["bones"]["head"]["rotation"] == [5, 0, 0]
    assert pose["bones"]["spine"]["rotation"] == [0, 1, 0]