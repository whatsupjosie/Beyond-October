"""Live-spine integration tests for the mounted PubPartner vessel."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_vessel import PubPartnerVesselRuntime


class VesselSpineIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vessel = PubPartnerVesselRuntime.create(
            self.root / "vessels" / "alex.pubpartner"
        )
        self.spine = PubPartnerSpine(self.root, vessel_runtime=self.vessel)

    async def test_large_vessel_reaches_provider_prompt_intact(self):
        marker = "complete identity " * 1500 + "IDENTITY_END"
        self.vessel.store.set_identity("self_concept", marker, authority="owner")
        for provider in ("local", "mock"):
            turn = await self.spine.build_turn_packet(
                user_id="user:owner", session_id="session:one", message="Hello",
                friend="alex", provider={"provider": provider}, room_id="phone",
            )
            self.assertEqual(turn["fcp1"]["vessel"]["identity"]["self_concept"], marker)
            self.assertIn("IDENTITY_END", turn["llm_prompt_text"])
            self.assertIn("rules=", turn["fcp1"]["vessel"]["prompt_text"])
            self.assertEqual(turn["fcp1"]["vessel"]["budget"], "generous")

    async def test_default_session_mounts_alex_from_vessel(self) -> None:
        session = await self.spine.create_session(
            user_id="user:owner",
            session_id="session:one",
        )
        self.assertEqual(session["friend"]["id"], "alex")
        self.assertEqual(session["friend"]["name"], "Alex")

    async def test_current_turn_is_not_available_as_prior_memory(self) -> None:
        turn = await self.spine.build_turn_packet(
            user_id="user:owner",
            session_id="session:one",
            message="I played softball at a picnic once.",
            friend="alex",
            provider={"provider": "mock"},
            room_id="phone",
        )
        vessel = turn["fcp1"]["vessel"]
        self.assertEqual(vessel["claims"], [])
        self.assertEqual(vessel["events"], [])
        self.assertEqual(turn["vessel_recorded_event_id"], "")
        with self.vessel.store.reader() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM memory_events").fetchone()[0], 0)
        self.assertIn("vessel=", turn["llm_prompt_text"])

    async def test_explicit_shared_history_is_relevant_not_omnipresent(self) -> None:
        learned = await self.spine.run_turn(
            user_id="user:owner",
            session_id="session:one",
            message="Remember that I played softball once.",
            friend="alex",
            provider={"provider": "mock"},
            room_id="phone",
        )
        claims = learned["relationship"]["vessel_claims"]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["status"], "confirmed")

        soup = await self.spine.build_turn_packet(
            user_id="user:owner",
            session_id="session:one",
            message="Help me improve tomato soup.",
            friend="alex",
            provider={"provider": "mock"},
            room_id="phone",
        )
        self.assertEqual(soup["fcp1"]["vessel"]["claims"], [])
        self.assertFalse(
            any(
                "softball" in str(row.get("text") or "").casefold()
                for row in soup["fcp1"]["guide"]
            )
        )

        softball = await self.spine.build_turn_packet(
            user_id="user:owner",
            session_id="session:one",
            message="What did I say about softball?",
            friend="alex",
            provider={"provider": "mock"},
            room_id="phone",
        )
        self.assertEqual(len(softball["fcp1"]["vessel"]["claims"]), 1)

    async def test_private_memory_is_withheld_on_pubcast_stage(self) -> None:
        await self.spine.run_turn(
            user_id="user:owner",
            session_id="session:private",
            message="Remember that my private launch phrase is bluebird.",
            friend="alex",
            provider={"provider": "mock"},
            room_id="phone",
        )
        stage = await self.spine.build_turn_packet(
            user_id="user:owner",
            session_id="session:stage",
            message="Say something about my bluebird launch phrase.",
            friend="alex",
            provider={"provider": "mock"},
            room_id="bar_stage",
            task={"audience": "shared"},
        )
        vessel = stage["fcp1"]["vessel"]
        self.assertEqual(vessel["audience"], "shared")
        self.assertEqual(vessel["claims"], [])
        self.assertEqual(vessel["events"], [])
        self.assertTrue(vessel["relationship"]["private_state_withheld"])
        self.assertEqual(stage["fcp1"]["guide"], [])

    async def test_explicit_non_vessel_friend_does_not_receive_alex_vessel(self) -> None:
        turn = await self.spine.build_turn_packet(
            user_id="user:owner",
            session_id="session:craig",
            message="Hello Craig.",
            friend="craig",
            provider={"provider": "mock"},
            room_id="phone",
        )
        self.assertEqual(turn["fcp1"]["f"]["id"], "craig")
        self.assertEqual(turn["fcp1"]["vessel"], {})
        self.assertEqual(turn["vessel_recorded_event_id"], "")


if __name__ == "__main__":
    unittest.main()
