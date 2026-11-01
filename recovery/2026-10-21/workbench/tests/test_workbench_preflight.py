"""Keep the packaged offline preflight runnable and non-destructive."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_preflight_checks_real_reach_routes_and_assets():
    result = subprocess.run([sys.executable, str(ROOT / 'tools/workbench_preflight.py')],
                            cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (result.stdout + '\n' + result.stderr)[-4000:]
    assert 'PREFLIGHT PASS' in result.stdout
    assert 'Reach page /writers-room' in result.stdout
    assert 'Reach page /pubpartner' in result.stdout
