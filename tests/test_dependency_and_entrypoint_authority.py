from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_main_is_the_only_main_entrypoint_source():
    assert (ROOT / "main.py").is_file()
    assert not (ROOT / "modules" / "main.py").exists(), (
        "modules/main.py is a retired duplicate authority; restore behavior in root main.py instead"
    )


def test_corrected_requirements_is_only_a_compatibility_alias():
    text = (ROOT / "requirements_CORRECTED.txt").read_text(encoding="utf-8")
    active = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert active == ["-r requirements.txt"]


def test_canonical_requirements_cover_core_unguarded_runtime_imports():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for required in ("psutil", "websockets", "structlog", "bcrypt", "cryptography", "scikit-learn"):
        assert required in text
    assert "fastapi>=0.115.0,<0.116.0" in text
    assert "starlette>=0.41.0,<0.42.0" in text
    assert 'posix_ipc>=1.1.1; sys_platform != "win32"' in text


def test_active_tree_contains_no_source_backup_artifacts():
    patterns = ("*.bak", "*.orig", "*.old", "*.backup", "*.pre_*", "*~")
    found = []
    for pattern in patterns:
        found.extend(path.relative_to(ROOT).as_posix() for path in ROOT.rglob(pattern) if path.is_file())
    assert not sorted(set(found)), "stale source backups belong in handoff/archive evidence, not the active build"
