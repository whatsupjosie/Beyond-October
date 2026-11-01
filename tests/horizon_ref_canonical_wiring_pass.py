"""Canonical wiring pass regression tests.

These tests verify that the safe wiring pass does not blindly mount stale
systems, and that the newly activated Room Conductor is process
infrastructure with optional Bubble Stack context, not a character slot.
"""

from fastapi.testclient import TestClient


def test_room_conductor_factory_imports_and_has_bubble_hook():
    from modules.room_conductor import create_room_conductor, RoomConductor  # noqa: F401

    assert callable(create_room_conductor)
    assert hasattr(RoomConductor, "set_bubble_summary_provider")
    assert hasattr(RoomConductor, "get_stats")


def test_main_wires_room_conductor_without_guest_character_slot():
    import main

    with TestClient(main.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["systems"]["room_conductor"] is True

        status = client.get("/api/internal/room-conductor/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["internal_only"] is True
        assert payload["guest_visible"] is False
        assert payload["character_slot"] is False
        assert payload["bubble_context_provider"] is True
        assert payload["stats"]["characters_known"] >= 3

        # Core systems that must not regress.
        assert client.get("/api/bubble-stack/schema").status_code == 200
        assert client.get("/api/internal/pete/status").status_code == 200
        assert client.get("/api/cameras").status_code == 200
        assert client.get("/api/recording/profiles").status_code == 200
