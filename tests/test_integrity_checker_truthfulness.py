"""The background integrity checker must not claim a repair it did not make.

It used to record `restored=True` and log "corrupted and restored" for every failed check, although nothing in it (or
in the vault it watches) restores anything. Now a failed check is reported as detected and not repaired.
"""
from modules.integrity_checker import BackgroundIntegrityChecker


class Vault:
    owner_user = "owner"

    def __init__(self, results):
        self.results = results

    def verify_file_integrity(self, file_id, user):
        value = self.results[file_id]
        if isinstance(value, Exception):
            raise value
        return value


def test_a_failed_check_is_detected_not_restored():
    checker = BackgroundIntegrityChecker(Vault({"good": (True, "OK"), "bad": (False, "hash mismatch")}))
    good, bad = checker._check_file("good"), checker._check_file("bad")
    assert (good.checksum_valid, good.restored, good.state) == (True, False, "verified")
    assert (bad.checksum_valid, bad.restored, bad.state, bad.error) == (False, False, "corruption_detected", "hash mismatch")


def test_a_check_that_could_not_run_is_recorded_as_such():
    checker = BackgroundIntegrityChecker(Vault({"x": OSError("vault locked")}))
    result = checker._check_file("x")
    assert (result.state, result.restored, result.checksum_valid) == ("check_failed", False, False)
    assert "vault locked" in result.error


def test_statistics_never_report_restored_files_that_were_not_restored():
    checker = BackgroundIntegrityChecker(Vault({"good": (True, "OK"), "bad": (False, "x"), "err": RuntimeError("boom")}))
    for name in ("good", "bad", "err"):
        checker._check_file(name)
    stats = checker.get_statistics()
    assert stats["files_restored"] == 0
    assert (stats["corruption_detected"], stats["check_failures"], stats["failed_checks"], stats["total_checks"]) == (1, 1, 2, 3)
