"""Static product-law checks for the normalized Iteration Wallet spine."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "iteration_wallet"


def read(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


def test_active_package_has_expected_spine_modules():
    for name in [
        "app.py",
        "blackbox.py",
        "ceremony.py",
        "cli.py",
        "gatekeeper.py",
        "guard.py",
        "identity.py",
        "notification_manager.py",
        "server.py",
        "vault.py",
        "vault_v21.py",
    ]:
        assert (PACKAGE / name).exists(), name


def test_server_exposes_no_delete_route_or_delete_method():
    source = read("server.py").lower()
    assert "@app.delete" not in source
    assert "delete(" not in source
    assert "no_delete" in source


def test_vault_engine_moves_records_without_unlink_or_remove_item():
    source = read("vault_v21.py")
    assert ".unlink(" not in source
    assert "os.remove" not in source
    assert "shutil.rmtree" not in source
    assert "move_to_removed" in source
    assert "quarantine_file" in source


def test_no_retired_temporary_modules_remain_active():
    assert not (PACKAGE / "private_alpha_runner.py").exists()
    assert not (PACKAGE / "key_derivation.py").exists()


def test_compatibility_wrappers_do_not_own_duplicate_logic():
    app_source = read("app.py")
    guard_source = read("guard.py")
    vault_source = read("vault.py")
    assert "from iteration_wallet.server import app" in app_source
    assert "from iteration_wallet.gatekeeper import" in guard_source
    assert "from iteration_wallet.vault_v21 import" in vault_source


def test_blackbox_owns_human_intent_receipts():
    source = read("blackbox.py")
    assert "def issue_human_intent_receipt" in source
    assert "def verify_receipts" in source
    assert "Human Intent receipt" in source


def test_vault_protected_actions_return_receipts():
    source = read("vault_v21.py")
    assert "action_key=\"promote_candidate_to_prime\"" in source
    assert "action_key=\"remove_from_active\"" in source
    assert "action_key=\"quarantine\"" in source
    assert '"receipt": receipt' in source


def test_oubliette_mvp_boundary_is_documented_without_new_adapter():
    doc = ROOT / "docs" / "iteration_wallet" / "OUBLIETTE_MVP_BOUNDARY_20260628.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "No separate active Oubliette adapter" in text
    assert "quarantine/no-execute boundary" in text
