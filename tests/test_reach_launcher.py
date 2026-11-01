"""Regressions for two actionable launch failures, with disposable data."""
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_occupied_port_stops_before_boot_or_data_creation(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0));occupied.listen()
        result = subprocess.run([sys.executable, str(ROOT / "run_reach.py"), "--no-browser",
            "--port", str(occupied.getsockname()[1]), "--data-dir", str(tmp_path / "data")],
            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert "cannot use port" in result.stdout
    assert not (tmp_path / "data").exists()


def test_incomplete_extraction_gives_recovery_instructions(tmp_path):
    script = tmp_path / "start_reach.py"
    script.write_bytes((ROOT / "start_reach.py").read_bytes())
    result = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert "Extract All" in result.stdout
    assert not (tmp_path / ".reach-venv").exists()


def test_first_run_seeds_packaged_bot_configs_without_overwrite(tmp_path):
    sys.path.insert(0, str(ROOT))
    import run_reach

    data = tmp_path / "fresh"
    seeded = run_reach._seed_packaged_bot_configs(ROOT, data)
    assert set(seeded) == {"pete.json", "jeremy.json", "repeat.json", "sir_purfluous.json"}
    for name in seeded:
        assert (data / "bots" / name).read_bytes() == (ROOT / "data" / "bots" / name).read_bytes()

    custom = data / "bots" / "pete.json"
    custom.write_text('{"user_owned": true}', encoding="utf-8")
    seeded_again = run_reach._seed_packaged_bot_configs(ROOT, data)
    assert seeded_again == []
    assert custom.read_text(encoding="utf-8") == '{"user_owned": true}'
