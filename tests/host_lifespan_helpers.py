"""Run ownership/shutdown assertions outside the suite's session-owned host."""
import os
from pathlib import Path
import subprocess
import sys


def run_isolated_host(script, data_dir):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-c", script], cwd=root,
        env=dict(os.environ, PUBCAST_DATA_DIR=str(data_dir)),
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr[-8000:] + result.stdout[-2000:]
