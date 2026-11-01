from __future__ import annotations

import asyncio
import json
from pathlib import Path

from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_profiles import PubPartnerProfileStore
from modules.pubpartner_voice import AlexPersonalizationEngine

ROOT = Path(__file__).resolve().parents[1]


def test_alex_is_seeded_as_first_friend(tmp_path: Path):
    store = PubPartnerProfileStore(tmp_path)
    alex = store.load_profile("friend", "alex")
    assert alex["display_name"] == "Alex"
    assert "constant_fixing" in alex["avoid"]
    assert alex["mode_policy"]["sensitive_roleplay"]["activation"] == "explicit_only"


def test_ui_defaults_to_alex():
    html = (ROOT / "static" / "pubpartner.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "pubpartner.js").read_text(encoding="utf-8")
    assert '<option value="alex" selected>Alex</option>' in html
    assert "value || 'alex'" in js


def test_every_turn_runs_full_alex_analysis_and_personalization(tmp_path: Path):
    bridge = AlexJeremyBridge(tmp_path)
    spine = PubPartnerSpine(tmp_path, alex_bridge=bridge)

    async def run():
        await spine.create_session(user_id="josie", session_id="alex-turn", friend="alex", provider={"provider": "mock"})
        return await spine.run_turn(
            user_id="josie",
            session_id="alex-turn",
            message="I went to the gym again.",
            friend="alex",
            provider={"provider": "mock"},
        )

    result = asyncio.run(run())
    assert result["alex_bridge"]["analysis_source"] == "AlexCore.process_message"
    assert result["alex_bridge"]["private_memory_context_withheld"] is True
    assert result["voice_restoration"]["personalization_applied"] is True
    assert result["receipt"]["personalization"]["applied"] is True
    assert result["receipt"]["alex_analysis"]["source"] == "AlexCore.process_message"
    bridge.shutdown()


def test_noop_is_a_valid_personalization_result():
    engine = AlexPersonalizationEngine()
    result = engine.restore("Yes. The one you started with is blue.", friend={"id": "alex"})
    assert result.personalization_applied is True
    assert result.change_level == "none"
    assert result.friend_response == result.raw_response


def test_small_provider_cleanup_is_recorded_not_overstated():
    engine = AlexPersonalizationEngine()
    result = engine.restore("Sure, here's the useful answer.", friend={"id": "alex", "avoid": ["generic_assistant"]})
    assert result.change_level == "light_stylistic"
    assert "trim_assistant_boilerplate" in result.applied
    assert result.friend_response == "here's the useful answer."


def test_false_reassurance_and_fake_autobiography_are_visible_warnings():
    engine = AlexPersonalizationEngine()
    reassurance = engine.restore("Everything will be okay.")
    autobiography = engine.restore("When I was a kid, my teacher did that too.")
    assert any("false_reassurance" in item for item in reassurance.warnings)
    assert "I wish I could promise that" in reassurance.friend_response
    assert any("fake_autobiography" in item for item in autobiography.warnings)
    assert "I don't have a human past" in autobiography.friend_response


def test_protected_code_survives_mandatory_pass():
    code = "```python\nprint('exact')\n```"
    result = AlexPersonalizationEngine().restore("Sure, " + code)
    assert code in result.friend_response
    assert result.protected_text_preserved is True


def test_pubpartner_only_runtime_is_canonical_launcher_target():
    runner = (ROOT / "run_pubpartner.py").read_text(encoding="utf-8")
    app = (ROOT / "pubpartner_app.py").read_text(encoding="utf-8")
    assert 'uvicorn.run("pubpartner_app:app"' in runner
    assert "optional PubCast studio systems" in app
    assert "from main import" not in app


def test_windows_launchers_use_project_venv():
    bat = (ROOT / "RUN_PUBPARTNER_WINDOWS.bat").read_text(encoding="utf-8")
    ps1 = (ROOT / "run_pubpartner_windows.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in bat
    assert "-m venv .venv" in bat
    assert ".venv\\Scripts\\python.exe" in ps1


def test_archive_manifest_records_full_reads_without_packaging_raw_sources():
    manifest = json.loads((ROOT / "profiles" / "alex" / "alex_source_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 9
    assert all(item["full_read"] is True for item in manifest)
    assert all(item["raw_text_packaged"] is False for item in manifest)
    kinds = {item["file"]: item["classification"] for item in manifest}
    assert kinds["conversation 16.md.docx"] == "index only"
    assert kinds["conversation 11-15.md.docx"] == "synthetic/sample data"


def test_profile_pack_keeps_identity_mode_policy_and_source_evidence_separate():
    # The current Reach authority no longer carries a second static modes/exemplar
    # pack under profiles/alex.  Identity/provenance remain source artifacts, while
    # the live mode policy is seeded by PubPartnerProfileStore.  Assert those real
    # authorities rather than requiring retired duplicate files.
    from modules.pubpartner_profiles import DEFAULT_FRIENDS

    identity = json.loads((ROOT / "profiles" / "alex" / "identity.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "profiles" / "alex" / "alex_source_manifest.json").read_text(encoding="utf-8"))
    alex = DEFAULT_FRIENDS["alex"]

    assert identity["name"] == "Alex"
    assert alex["mode_policy"]["sensitive_roleplay"]["activation"] == "explicit_only"
    assert len(manifest) == 9
    assert all(item["full_read"] is True for item in manifest)
    assert all(item["raw_text_packaged"] is False for item in manifest)
    assert any(item["classification"] == "genuine historical conversation" for item in manifest)
    assert any(item["classification"] == "specialized mode material" for item in manifest)


def test_preflight_checks_minimal_app():
    text = (ROOT / "modules" / "pubpartner_preflight.py").read_text(encoding="utf-8")
    assert '"pubpartner_app.py": app / "pubpartner_app.py"' in text
