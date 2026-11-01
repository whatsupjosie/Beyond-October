"""Run the offline companion and EVO regression selection from repository root."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
tests = [
    "tests/test_companion_chat_entrypoint.py", "tests/test_companion_provider_bridge.py",
    "tests/test_companion_sync_durability.py", "tests/test_five_round_sync_transactions.py",
    "tests/test_companion_horizon_host.py",
    "tests/horizon_ref_pubpartner_app_control_plane_wiring.py",
    "tests/test_companion_recovery.py", "tests/test_companion_docking.py",
    "tests/pubpartner_core", "tests/pubpartner_federation", "tests/pubpartner_vessel",
    "tests/test_pub_partner_chat.py", "tests/horizon_ref_pubpartner_live_loop.py",
    "tests/horizon_ref_pubpartner_spine.py", "tests/horizon_ref_pubpartner_relationship_engine.py",
    "tests/horizon_ref_pubpartner_repair4_continuity.py", "tests/test_emotional_orchestrator.py",
    "tests/test_affect_dynamics.py", "tests/test_eq_transitions.py", "tests/test_emotional_consultation.py",
    *[str(path.relative_to(root)) for path in sorted((root / "tests").glob("test_evo_*.py"))],
    "tests/test_epete_lifecycle_deadlines.py", "tests/test_prosody_semantic_adapter.py",
    "tests/test_vdi_semantic_adapter.py", "tests/test_round9_evo_irm_bridge_contract.py",
]
environment = dict(os.environ)
environment["PYTHONPATH"] = os.pathsep.join([str(root), str(root / "pubpartner"),
                                          environment.get("PYTHONPATH", "")])
raise SystemExit(subprocess.call([sys.executable, "-W", "error::ResourceWarning", "-m", "pytest",
    "--noconftest", "-q", "--asyncio-mode=auto", *tests, *sys.argv[1:]], cwd=root, env=environment))
