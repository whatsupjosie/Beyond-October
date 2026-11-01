"""Standard-library regression and adversarial tests for PubPartner vessels."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from modules.pubpartner_vessel import (
    ClaimStatus,
    Literalness,
    PubPartnerVesselRuntime,
    VesselConflictError,
    VesselFormatError,
    VesselIntegrityError,
    VesselReadOnlyError,
    VesselStore,
    Visibility,
)
from modules.pubpartner_vessel.__main__ import main as vessel_cli


class VesselTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "alex.pubpartner"
        self.runtime = PubPartnerVesselRuntime.create(self.path)
        self.memory = self.runtime.memory

    def event(
        self,
        content: str,
        *,
        literalness: str = Literalness.LITERAL.value,
        source_ref: str = "",
        visibility: str = Visibility.PRIVATE_RELATIONSHIP.value,
        room_id: str = "private",
    ):
        return self.memory.record_event(
            actor_id="user:owner",
            subject_id="user:owner",
            event_type="conversation.user_turn",
            content=content,
            literalness=literalness,
            visibility=visibility,
            source_ref=source_ref,
            room_id=room_id,
            session_id="session:test",
        )

    def claim_from(
        self,
        event,
        *,
        predicate: str = "interest",
        text: str = "The user likes softball",
        proactive_use: bool = True,
        claim_type: str = "preference",
        scope: str = "global",
        explicit_confirmation: bool = False,
        independence_key: str = "",
        visibility: str = Visibility.PRIVATE_RELATIONSHIP.value,
    ):
        return self.memory.propose_claim(
            event_id=event.event_id,
            subject_id="user:owner",
            predicate=predicate,
            value=text,
            normalized_text=text,
            proactive_use=proactive_use,
            claim_type=claim_type,
            scope=scope,
            explicit_confirmation=explicit_confirmation,
            independence_key=independence_key,
            visibility=visibility,
        )


class VesselStorageTests(VesselTestCase):
    def test_create_reopen_validate_and_read_only(self) -> None:
        status = self.runtime.status()
        self.assertTrue(status["ok"])
        self.assertEqual(status["friend_id"], "alex")
        reopened = PubPartnerVesselRuntime.open(self.path, read_only=True)
        self.assertEqual(reopened.friend_profile()["display_name"], "Alex")
        with self.assertRaises(VesselReadOnlyError):
            reopened.store.set_identity("tone", ["different"])

    def test_context_compilation_does_not_rewrite_existing_relationship(self) -> None:
        self.runtime.compile_turn(
            user_id="user:owner",
            message="First contact",
            session_id="session:one",
            room_id="private",
        )
        first_entries = self.runtime.store.verify_audit()["entries"]
        self.runtime.compile_turn(
            user_id="user:owner",
            message="Second turn",
            session_id="session:one",
            room_id="private",
        )
        self.assertEqual(
            self.runtime.store.verify_audit()["entries"],
            first_entries,
        )

    def test_refuses_symlink_and_hardlink_mounts(self) -> None:
        symlink = self.path.with_name("linked.pubpartner")
        symlink.symlink_to(self.path)
        with self.assertRaises(VesselFormatError):
            VesselStore.open(symlink)

        hardlink = self.path.with_name("hardlinked.pubpartner")
        os.link(self.path, hardlink)
        with self.assertRaises(VesselFormatError):
            VesselStore.open(self.path)
        hardlink.unlink()

    def test_asset_deduplication_binding_and_integrity(self) -> None:
        first = self.runtime.store.put_asset(
            b"voice-model-data", media_type="application/octet-stream"
        )
        second = self.runtime.store.put_asset(
            b"voice-model-data", media_type="application/octet-stream"
        )
        self.assertEqual(first["sha256"], second["sha256"])
        binding = self.runtime.store.bind_asset("voice.primary", first["sha256"])
        self.assertEqual(binding["asset_sha256"], first["sha256"])
        self.assertEqual(
            self.runtime.store.get_asset(first["sha256"])["content"],
            b"voice-model-data",
        )

        connection = sqlite3.connect(self.path)
        connection.execute(
            "UPDATE assets SET content = ? WHERE sha256 = ?",
            (b"corrupt", first["sha256"]),
        )
        connection.commit()
        connection.close()
        with self.assertRaises(VesselIntegrityError):
            self.runtime.store.get_asset(first["sha256"])

    def test_audit_tampering_is_detected(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute(
            "UPDATE audit_events SET record_id = 'tampered' WHERE sequence = 1"
        )
        connection.commit()
        connection.close()
        with self.assertRaises(VesselIntegrityError):
            VesselStore.open(self.path)

    def test_logical_state_tampering_is_detected(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute(
            "UPDATE identity_records SET value_json = '\"Mallory\"' "
            "WHERE key = 'display_name'"
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(VesselIntegrityError, "integrity seal mismatch"):
            VesselStore.open(self.path)

    def test_missing_record_seal_is_detected(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute(
            "DELETE FROM record_integrity "
            "WHERE table_name = 'identity_records' AND record_id = 'display_name'"
        )
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(VesselIntegrityError, "seal is missing"):
            VesselStore.open(self.path)

    def test_backup_is_consistent_validated_and_non_overwriting(self) -> None:
        self.event("A preserved observation.", source_ref="turn:backup")
        destination = self.path.with_name("alex-backup.pubpartner")
        result = self.runtime.store.backup_to(destination)
        self.assertTrue(result["ok"])
        original = self.runtime.store.validate()
        backup = VesselStore.open(destination, read_only=True).validate()
        self.assertEqual(
            backup["state_integrity"]["state_hash"],
            original["state_integrity"]["state_hash"],
        )
        self.assertEqual(backup["vessel_id"], original["vessel_id"])
        with self.assertRaises(VesselConflictError):
            self.runtime.store.backup_to(destination)

    def test_failed_transaction_rolls_back_without_partial_record(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.runtime.store.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO entities
                        (entity_id, entity_type, display_name, aliases_json,
                         metadata_json, created_at, updated_at)
                    VALUES ('partial', 'human', 'Partial', '[]', '{}', 1, 1)
                    """
                )
                raise RuntimeError("simulated crash before commit")
        with self.runtime.store.reader() as connection:
            row = connection.execute(
                "SELECT 1 FROM entities WHERE entity_id = 'partial'"
            ).fetchone()
        self.assertIsNone(row)
        self.assertTrue(self.runtime.store.validate()["ok"])

    def test_future_schema_is_rejected_without_mutation(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA user_version = 999")
        connection.commit()
        connection.close()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(VesselFormatError, "unsupported vessel schema"):
            VesselStore.open(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_event_writes_are_serialized_without_loss(self) -> None:
        errors: list[BaseException] = []
        barrier = threading.Barrier(8)

        def write(index: int) -> None:
            try:
                barrier.wait(timeout=5)
                self.event(
                    f"concurrent observation {index}",
                    source_ref=f"source:{index}",
                )
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(errors, errors)
        with self.runtime.store.reader() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM memory_events"
            ).fetchone()[0]
        self.assertEqual(count, 8)
        self.assertTrue(self.runtime.store.validate()["ok"])


class VesselCliTests(unittest.TestCase):
    def test_create_verify_and_backup_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "morgan.pubpartner"
            backup = Path(directory) / "morgan-backup.pubpartner"
            output = StringIO()
            with redirect_stdout(output):
                created = vessel_cli(
                    [
                        "create",
                        str(source),
                        "--friend-id",
                        "morgan",
                        "--display-name",
                        "Morgan",
                    ]
                )
                verified = vessel_cli(["verify", str(source)])
                copied = vessel_cli(["backup", str(source), str(backup)])
            self.assertEqual((created, verified, copied), (0, 0, 0))
            payloads = output.getvalue()
            self.assertIn('"friend_id": "morgan"', payloads)
            self.assertIn('"ok": true', payloads)
            self.assertTrue(VesselStore.open(backup, read_only=True).validate()["ok"])


class EvidenceMemoryTests(VesselTestCase):
    def test_one_anecdote_never_becomes_retrievable_identity(self) -> None:
        event = self.event("I played softball once at a family picnic.")
        claim = self.claim_from(event)
        self.assertEqual(claim.status, ClaimStatus.TENTATIVE.value)
        self.assertEqual(
            self.memory.retrieve_claims(
                subject_id="user:owner",
                viewer_id="user:owner",
                query="Tell me about softball",
                room_id="private",
            ),
            [],
        )

    def test_duplicate_evidence_cannot_manufacture_confidence(self) -> None:
        first = self.event("I like softball.", source_ref="turn:1")
        claim = self.claim_from(first, independence_key="turn:1")
        for index in range(5):
            duplicate = self.event(
                f"Repeated copy {index}: I like softball.",
                source_ref=f"copy:{index}",
            )
            claim = self.memory.add_evidence(
                claim.claim_id,
                event_id=duplicate.event_id,
                independence_key="turn:1",
            )
        self.assertEqual(claim.status, ClaimStatus.TENTATIVE.value)
        self.assertEqual(claim.support_count, 1)

    def test_joke_is_low_weight_and_does_not_promote(self) -> None:
        claim = None
        for index in range(5):
            event = self.event(
                f"Joke {index}: softball is literally my entire personality.",
                literalness=Literalness.JOKING.value,
                source_ref=f"joke:{index}",
            )
            if claim is None:
                claim = self.claim_from(event, independence_key=f"joke:{index}")
            else:
                claim = self.memory.add_evidence(
                    claim.claim_id,
                    event_id=event.event_id,
                    independence_key=f"joke:{index}",
                )
        assert claim is not None
        self.assertEqual(claim.status, ClaimStatus.TENTATIVE.value)
        self.assertEqual(claim.support_count, 0)

    def test_independent_support_promotes_in_stages(self) -> None:
        first = self.event("I enjoy softball.", source_ref="turn:1")
        claim = self.claim_from(first, independence_key="turn:1")
        second = self.event("Softball is one sport I like.", source_ref="turn:2")
        claim = self.memory.add_evidence(
            claim.claim_id, event_id=second.event_id, independence_key="turn:2"
        )
        self.assertEqual(claim.status, ClaimStatus.CORROBORATED.value)
        third = self.event("Yes, I still like softball.", source_ref="turn:3")
        claim = self.memory.add_evidence(
            claim.claim_id, event_id=third.event_id, independence_key="turn:3"
        )
        self.assertEqual(claim.status, ClaimStatus.CONFIRMED.value)

    def test_explicit_confirmation_promotes_directly(self) -> None:
        event = self.event("Yes, save this: I like softball.")
        claim = self.claim_from(event, explicit_confirmation=True)
        self.assertEqual(claim.status, ClaimStatus.CONFIRMED.value)
        self.assertGreaterEqual(claim.confidence, 0.95)

    def test_rejection_blocks_retrieval_and_silent_reactivation(self) -> None:
        event = self.event("Yes, save this: I like softball.")
        claim = self.claim_from(event, explicit_confirmation=True)
        corrected = self.memory.correct_claim(
            claim.claim_id,
            action="reject",
            reason="That was sarcasm and is not true.",
        )
        self.assertEqual(corrected.status, ClaimStatus.REJECTED.value)
        self.assertEqual(
            self.memory.retrieve_claims(
                subject_id="user:owner",
                viewer_id="user:owner",
                query="softball",
                room_id="private",
            ),
            [],
        )
        later = self.event("An unrelated mention of softball.")
        with self.assertRaises(VesselConflictError):
            self.claim_from(later)

    def test_replace_updates_claim_value_and_text_together(self) -> None:
        event = self.event("Yes, save this: I like softball.")
        claim = self.claim_from(event, explicit_confirmation=True)

        corrected = self.memory.correct_claim(
            claim.claim_id,
            action="replace",
            replacement_text="The user occasionally plays softball",
            reason="The original wording was too broad.",
        )

        self.assertEqual(
            corrected.value, "The user occasionally plays softball"
        )
        self.assertEqual(
            corrected.normalized_text,
            "The user occasionally plays softball",
        )

    def test_correction_event_must_have_same_subject_as_claim(self) -> None:
        event = self.event("Yes, save this: I like softball.")
        claim = self.claim_from(event, explicit_confirmation=True)
        other = self.memory.record_event(
            actor_id="user:other",
            subject_id="user:other",
            event_type="conversation.user_turn",
            content="Other user's correction.",
            literalness=Literalness.LITERAL.value,
        )

        with self.assertRaisesRegex(
            VesselConflictError, "subject does not match"
        ):
            self.memory.correct_claim(
                claim.claim_id,
                action="reject",
                reason="Wrong provenance.",
                event_id=other.event_id,
            )

    def test_replace_collision_is_reported_as_vessel_conflict(self) -> None:
        first = self.event("I like softball.", source_ref="turn:first")
        first_claim = self.claim_from(
            first,
            text="The user likes softball",
            explicit_confirmation=True,
        )
        second = self.event("I sometimes play softball.", source_ref="turn:second")
        self.claim_from(
            second,
            text="The user sometimes plays softball",
            explicit_confirmation=True,
        )

        with self.assertRaisesRegex(VesselConflictError, "existing memory claim"):
            self.memory.correct_claim(
                first_claim.claim_id,
                action="replace",
                replacement_text="The user sometimes plays softball",
                reason="Narrow the preference.",
            )

    def test_relevance_prevents_softball_from_invading_other_topics(self) -> None:
        event = self.event("Yes, save this: I like softball.")
        self.claim_from(event, explicit_confirmation=True)
        irrelevant = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="How should I make tomato soup?",
            room_id="private",
        )
        relevant = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="Do you remember which softball sport I like?",
            room_id="private",
        )
        self.assertEqual(irrelevant, [])
        self.assertEqual(len(relevant), 1)

    def test_global_boundaries_are_relevant_without_keyword_overlap(self) -> None:
        event = self.event("Never share my home address.")
        self.claim_from(
            event,
            predicate="privacy_boundary",
            text="Never share the user's home address",
            explicit_confirmation=True,
            claim_type="boundary",
        )
        retrieved = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="Write a recipe",
            room_id="private",
        )
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["claim_type"], "boundary")

    def test_private_and_room_scoped_visibility_do_not_leak(self) -> None:
        private_event = self.event("My private launch phrase is bluebird.")
        self.claim_from(
            private_event,
            predicate="private_phrase",
            text="The user's private launch phrase is bluebird",
            explicit_confirmation=True,
        )
        self.assertEqual(
            self.memory.retrieve_claims(
                subject_id="user:owner",
                viewer_id="user:other",
                query="bluebird launch phrase",
                room_id="private",
            ),
            [],
        )

        room_event = self.event(
            "In this room, call the project Lantern.",
            visibility=Visibility.ROOM_SCOPED.value,
            room_id="room:alpha",
        )
        self.claim_from(
            room_event,
            predicate="project_name",
            text="The project is called Lantern",
            explicit_confirmation=True,
            scope="room:room:alpha",
            visibility=Visibility.ROOM_SCOPED.value,
        )
        visible = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="Lantern project",
            room_id="room:alpha",
        )
        hidden = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="Lantern project",
            room_id="room:beta",
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(hidden, [])

    def test_private_memory_is_withheld_in_shared_audience(self) -> None:
        event = self.event("Yes, save this: my private phrase is bluebird.")
        self.claim_from(
            event,
            predicate="private_phrase",
            text="The user's private phrase is bluebird",
            explicit_confirmation=True,
        )
        private = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="bluebird phrase",
            room_id="phone",
            audience="private",
        )
        shared = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="bluebird phrase",
            room_id="studio",
            audience="shared",
        )
        self.assertEqual(len(private), 1)
        self.assertEqual(shared, [])

    def test_project_and_session_scopes_do_not_cross_boundaries(self) -> None:
        event = self.event("Use the codename Lantern in Project A.")
        project_claim = self.claim_from(
            event,
            predicate="project_codename",
            text="Project A is codenamed Lantern",
            explicit_confirmation=True,
            scope="project:a",
        )
        self.assertEqual(project_claim.status, ClaimStatus.CONFIRMED.value)
        visible = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="Lantern codename",
            project_id="a",
        )
        hidden = self.memory.retrieve_claims(
            subject_id="user:owner",
            viewer_id="user:owner",
            query="Lantern codename",
            project_id="b",
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(hidden, [])

    def test_context_is_bounded_and_excludes_irrelevant_claims(self) -> None:
        event = self.event("Yes, save this: I like softball.")
        self.claim_from(event, explicit_confirmation=True)
        context = self.runtime.compile_turn(
            user_id="user:owner",
            message="Help me improve a tomato soup recipe.",
            session_id="session:test",
            room_id="private",
            budget_profile="gemma_e2b",
        )
        self.assertLessEqual(len(context.prompt_text), 4_000)
        self.assertEqual(context.claims, [])
        self.assertNotIn("likes softball", context.prompt_text)
        self.assertEqual(len(context.context_hash), 64)

    def test_context_hash_is_deterministic_for_unchanged_state(self) -> None:
        first = self.runtime.compile_turn(
            user_id="user:owner",
            message="Help with soup.",
            session_id="session:test",
            room_id="private",
        )
        second = self.runtime.compile_turn(
            user_id="user:owner",
            message="Help with soup.",
            session_id="session:test",
            room_id="private",
        )
        self.assertEqual(first.context_hash, second.context_hash)
        self.assertEqual(first.prompt_text, second.prompt_text)


if __name__ == "__main__":
    unittest.main()
