"""Real-file recovery checks; standard-library runner needs no app dependencies."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from modules import data_checkpoint as checkpoint
from modules.data_checkpoint import (CheckpointError, Limits, create_checkpoint,
                                     restore_checkpoint, verify_checkpoint)

ROOT = Path(__file__).resolve().parents[1]


class DataCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.data = self.base / "owner data"
        self.data.mkdir()
        for name, content in {
            "secure/jwt_secret.txt": b"DISPOSABLE-TEST-KEY",
            "vault/private.bin": bytes(range(256)) * 12,
            "recordings/take/source.webm": b"DISPOSABLE-SOURCE-BYTES",
            "users/writer/manuscript.txt": "Exact words.\n  café 🎭\r\n".encode(),
            "studio_progress/owner.json": b'{"room":"green_room"}',
        }.items():
            path = self.data / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (self.data / "empty-folder").mkdir()
        self.archive = self.base / "private.zip"

    def create(self, **options):
        return create_checkpoint(self.data, self.archive, offline=True, **options)

    def rewrite(self, change):
        with zipfile.ZipFile(self.archive) as archive:
            entries = [(item, archive.read(item)) for item in archive.infolist()]
        with zipfile.ZipFile(self.archive, "w") as archive:
            for info, content in entries:
                result = change(info, content)
                if result is not None:
                    archive.writestr(*result)

    def manifest_change(self, change):
        def transform(info, content):
            if info.filename == checkpoint.MANIFEST:
                value = json.loads(content)
                change(value)
                content = json.dumps(value).encode()
            return info, content
        self.rewrite(transform)

    def test_full_exact_round_trip_includes_keys_media_and_empty_directories(self):
        before = {p.relative_to(self.data): p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        receipt = self.create(source_revision="known-source")
        result = restore_checkpoint(self.archive, self.base / "recovered", expected_sha256=receipt["sha256"])
        restored = Path(result["data_dir"])
        self.assertEqual({p.relative_to(restored): p.read_bytes() for p in restored.rglob("*") if p.is_file()}, before)
        self.assertTrue((restored / "empty-folder").is_dir())
        self.assertEqual(receipt["source_revision"], "known-source")
        self.assertEqual(json.loads(Path(result["receipt"]).read_text())["sha256"], receipt["sha256"])
        self.assertEqual(verify_checkpoint(self.archive)["file_count"], len(before))

    def test_refuses_capture_without_explicit_stopped_writer_confirmation(self):
        with self.assertRaisesRegex(CheckpointError, "--offline"):
            create_checkpoint(self.data, self.archive)
        self.assertFalse(self.archive.exists())

    def test_missing_data_directory_is_not_created(self):
        missing = self.base / "misspelled"
        with self.assertRaises(CheckpointError):
            create_checkpoint(missing, self.archive, offline=True)
        self.assertFalse(missing.exists())

    def test_output_inside_source_is_refused(self):
        with self.assertRaisesRegex(CheckpointError, "outside"):
            create_checkpoint(self.data, self.data / "backups" / "file.zip", offline=True)
        self.assertFalse((self.data / "backups").exists())

    def test_existing_archive_is_preserved(self):
        self.archive.write_bytes(b"previous checkpoint")
        with self.assertRaises(CheckpointError):
            self.create()
        self.assertEqual(self.archive.read_bytes(), b"previous checkpoint")

    def test_existing_restore_destination_even_empty_is_preserved(self):
        self.create()
        destination = self.base / "existing"
        destination.mkdir()
        with self.assertRaises(CheckpointError):
            restore_checkpoint(self.archive, destination)
        self.assertEqual(list(destination.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX mode bits; Windows ACLs require commissioning")
    def test_created_archive_and_restored_files_are_private(self):
        self.create()
        result = restore_checkpoint(self.archive, self.base / "recovered")
        self.assertEqual(stat.S_IMODE(self.archive.stat().st_mode), 0o600)
        for path in Path(result["data_dir"]).rglob("*"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    @unittest.skipIf(os.name == "nt", "symlink privilege varies on Windows")
    def test_file_and_directory_links_are_refused(self):
        for directory in (False, True):
            with self.subTest(directory=directory):
                link = self.data / "link"
                link.symlink_to(self.data / ("vault" if directory else "secure/jwt_secret.txt"), target_is_directory=directory)
                with self.assertRaises(CheckpointError):
                    self.create()
                link.unlink()
                self.assertFalse(self.archive.exists())

    @unittest.skipIf(not hasattr(os, "mkfifo"), "requires FIFO support")
    def test_fifo_is_refused_without_blocking(self):
        os.mkfifo(self.data / "pipe")
        with self.assertRaises(CheckpointError):
            self.create()

    def test_nonportable_paths_and_collisions_are_refused(self):
        for names in (["con.txt"], ["bad:stream"], ["trailing."], ["Case", "case"], ["é", "é"]):
            with self.subTest(names=names):
                value = {"format": checkpoint.FORMAT, "offline": True, "private_runtime_data": True,
                         "directories": [], "files": [{"path": n, "size": 0, "mtime_ns": 0,
                                                         "sha256": hashlib.sha256(b"").hexdigest()} for n in names]}
                with self.assertRaises(CheckpointError):
                    checkpoint._validate_manifest(value, Limits())

    def test_same_length_corruption_is_detected_by_hash(self):
        self.create()
        def corrupt(info, content):
            if info.filename == "data/secure/jwt_secret.txt":
                content = bytes([content[0] ^ 1]) + content[1:]
            return info, content
        self.rewrite(corrupt)
        with self.assertRaisesRegex(CheckpointError, "SHA-256 mismatch"):
            verify_checkpoint(self.archive)
        destination = self.base / "refused"
        with self.assertRaises(CheckpointError):
            restore_checkpoint(self.archive, destination)
        self.assertFalse(destination.exists())

    def test_external_digest_rejects_a_rewritten_manifest_and_payload(self):
        receipt = self.create()
        self.manifest_change(lambda m: m.update(source_revision="changed"))
        with self.assertRaisesRegex(CheckpointError, "trusted digest"):
            verify_checkpoint(self.archive, expected_sha256=receipt["sha256"])

    def test_extra_and_duplicate_zip_members_are_refused(self):
        self.create()
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("unlisted", b"hidden")
        with self.assertRaisesRegex(CheckpointError, "complete manifest"):
            verify_checkpoint(self.archive)
        self.archive.unlink()
        self.create()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "a") as archive:
                archive.writestr(checkpoint.MANIFEST, b"{}")
        with self.assertRaisesRegex(CheckpointError, "Duplicate ZIP"):
            verify_checkpoint(self.archive)

    def test_traversal_absolute_and_backslash_names_are_refused(self):
        self.create()
        for name in ("../escape", "/absolute", "C:/drive", "a\\b", "x//y", "x/./y"):
            with self.subTest(name=name), self.assertRaises(CheckpointError):
                checkpoint._path(name)

    def test_inventory_requires_real_parent_directories(self):
        self.create()
        self.manifest_change(lambda m: m.update(directories=[]))
        with self.assertRaisesRegex(CheckpointError, "parent directory"):
            verify_checkpoint(self.archive)

    def test_archive_symlink_is_refused(self):
        self.create()
        def link(info, content):
            if info.filename.startswith("data/"):
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            return info, content
        self.rewrite(link)
        with self.assertRaisesRegex(CheckpointError, "member type"):
            verify_checkpoint(self.archive)

    def test_manifest_size_count_and_byte_limits(self):
        self.create()
        for limits in (Limits(max_manifest_bytes=20), Limits(max_files=1), Limits(max_bytes=1)):
            with self.subTest(limits=limits), self.assertRaises(CheckpointError):
                verify_checkpoint(self.archive, limits=limits)
        for options in ({"max_files": 0}, {"max_bytes": -1}):
            with self.assertRaises(CheckpointError):
                Limits(**options)

    def test_source_mutation_aborts_without_publishing(self):
        original_scan = checkpoint._scan
        calls = 0
        def mutate(root, limits):
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.data / "new-save.txt").write_text("changed while capturing")
            return original_scan(root, limits)
        with patch.object(checkpoint, "_scan", side_effect=mutate), self.assertRaisesRegex(CheckpointError, "changed"):
            self.create()
        self.assertFalse(self.archive.exists())
        self.assertEqual(list(self.base.glob(".pubcast-checkpoint-*")), [])

    def test_disk_full_keeps_previous_data_and_cleans_partial_capture(self):
        with patch.object(checkpoint, "_transfer", side_effect=OSError(errno.ENOSPC, "test disk full")):
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse(self.archive.exists())
        self.assertTrue((self.data / "secure/jwt_secret.txt").exists())
        self.assertEqual(list(self.base.glob(".pubcast-checkpoint-*")), [])

    def test_publication_never_replaces_a_racing_archive(self):
        real_link = os.link
        def racing_link(source, target):
            Path(target).write_bytes(b"other writer won")
            return real_link(source, target)
        with patch.object(checkpoint.os, "link", side_effect=racing_link), self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(self.archive.read_bytes(), b"other writer won")

    def test_two_restore_calls_have_exactly_one_winner(self):
        self.create()
        destination = self.base / "same destination"
        def attempt(_):
            try:
                return restore_checkpoint(self.archive, destination)["ok"]
            except (CheckpointError, FileExistsError):
                return False
        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, range(2))), [False, True])
        self.assertEqual((destination / "data/secure/jwt_secret.txt").read_bytes(), b"DISPOSABLE-TEST-KEY")

    def test_sqlite_committed_wal_survives_cold_relocation(self):
        database = self.data / "conversation.db"
        script = "import sqlite3,os,sys; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL'); c.execute('CREATE TABLE saved(text)'); c.execute('INSERT INTO saved VALUES (?)', ('verbatim saved turn',)); c.commit(); os._exit(0)"
        subprocess.run([sys.executable, "-c", script, str(database)], check=True)
        self.assertGreater(Path(str(database) + "-wal").stat().st_size, 0)
        self.create()
        result = restore_checkpoint(self.archive, self.base / "wal recovered")
        with closing(sqlite3.connect(Path(result["data_dir"]) / "conversation.db")) as database:
            self.assertEqual(database.execute("SELECT text FROM saved").fetchall(), [("verbatim saved turn",)])
            self.assertEqual(database.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_existing_product_stores_reopen_from_restored_directory(self):
        from modules.conversation_archive import ConversationArchive
        from modules import documents
        source = ConversationArchive(self.data / "archive.sqlite")
        conversation = source.create_conversation(title="Pilot", metadata={"owner": "owner"})
        exact = "  Keep every word.\nCafé 🎭\n"
        source.append_message(conversation, speaker="owner", exact_text=exact)
        manuscript = documents.upsert_document(self.data, "owner", {"title": "Draft", "content": exact})
        self.create()
        result = restore_checkpoint(self.archive, self.base / "stores recovered")
        restored = Path(result["data_dir"])
        archive = ConversationArchive(restored / "archive.sqlite")
        self.assertEqual(archive.get_conversation(conversation)["messages"][0]["exact_text"], exact)
        self.assertEqual([row["conversation_id"] for row in archive.list_conversations_for_owner("owner")], [conversation])
        self.assertEqual(archive.list_conversations_for_owner("someone-else"), [])
        self.assertEqual(documents.get_document(restored, "owner", manuscript["doc_id"])["content"], exact)

    def test_cli_runs_from_another_working_directory_without_app_dependencies(self):
        tool = ROOT / "tools/pubcast_checkpoint.py"
        def run(*arguments):
            result = subprocess.run([sys.executable, str(tool), *arguments], cwd=self.base,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        receipt = run("create", "--data-dir", str(self.data), "--output", str(self.archive), "--offline")
        self.assertTrue(run("verify", "--archive", str(self.archive), "--expected-sha256", receipt["sha256"])["ok"])
        result = run("restore", "--archive", str(self.archive), "--destination", str(self.base / "cli recovery"))
        self.assertTrue(Path(result["data_dir"]).is_dir())
        refused = subprocess.run([sys.executable, str(tool), "create", "--data-dir", str(self.data),
                                  "--output", str(self.base / "unsafe.zip")], cwd=self.base, capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)
        self.assertFalse(json.loads(refused.stderr)["ok"])

    def test_truncated_archive_is_refused_without_creating_destination(self):
        self.create()
        self.archive.write_bytes(self.archive.read_bytes()[:90])
        with self.assertRaises(CheckpointError):
            restore_checkpoint(self.archive, self.base / "bad recovery")
        self.assertFalse((self.base / "bad recovery").exists())

    def test_duplicate_manifest_keys_are_refused(self):
        self.create()
        def duplicate(info, content):
            if info.filename == checkpoint.MANIFEST:
                content = content.replace(b'{', b'{"format":"duplicate",', 1)
            return info, content
        self.rewrite(duplicate)
        with self.assertRaisesRegex(CheckpointError, "Duplicate manifest field"):
            verify_checkpoint(self.archive)

    def test_restore_failure_before_publication_cleans_staging(self):
        self.create()
        original = checkpoint._transfer
        def fail_extraction(source, destination, **options):
            if destination is not None:
                raise OSError(errno.ENOSPC, "test extraction disk full")
            return original(source, destination, **options)
        with patch.object(checkpoint, "_transfer", side_effect=fail_extraction), self.assertRaises(OSError):
            restore_checkpoint(self.archive, self.base / "no partial data")
        self.assertFalse((self.base / "no partial data").exists())
        self.assertEqual(list(self.base.glob(".pubcast-restore-*")), [])

    def test_empty_tree_has_a_valid_restorable_inventory(self):
        empty = self.base / "empty"
        empty.mkdir()
        result = create_checkpoint(empty, self.archive, offline=True)
        self.assertEqual(result["file_count"], 0)
        self.assertEqual(result["bytes"], 0)
        restored = restore_checkpoint(self.archive, self.base / "empty restored")
        self.assertEqual(list(Path(restored["data_dir"]).iterdir()), [])

    def test_source_change_during_archive_verification_is_detected(self):
        original = checkpoint.verify_checkpoint
        def mutate(*arguments, **options):
            result = original(*arguments, **options)
            (self.data / "late-save.txt").write_text("A writer was still running")
            return result
        with patch.object(checkpoint, "verify_checkpoint", side_effect=mutate), self.assertRaisesRegex(CheckpointError, "Source changed"):
            self.create()
        self.assertFalse(self.archive.exists())

    def test_failed_directory_publication_has_no_success_receipt(self):
        self.create()
        destination = self.base / "interrupted publication"
        with patch.object(checkpoint.os, "rename", side_effect=OSError("test publication interrupted")), self.assertRaises(OSError):
            restore_checkpoint(self.archive, destination)
        self.assertFalse((destination / "PUBCAST_RESTORE.json").exists())
        self.assertTrue((destination / ".restore-pending.json").exists())
        self.assertFalse((destination / "data").exists())
        self.assertTrue(verify_checkpoint(self.archive)["ok"])

    def test_unsupported_atomic_archive_publication_fails_without_fallback_overwrite(self):
        with patch.object(checkpoint.os, "link", side_effect=OSError(errno.ENOTSUP, "no hard links")), self.assertRaises(OSError):
            self.create()
        self.assertFalse(self.archive.exists())
        self.assertEqual(list(self.base.glob(".pubcast-checkpoint-*")), [])


if __name__ == "__main__":
    unittest.main()
