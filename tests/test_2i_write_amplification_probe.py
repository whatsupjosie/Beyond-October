"""Run tools/2i_write_amplification_probe.cjs as part of the suite.

The probe drives the real Foresight persist()/persistRaw() source with a mock record store. It is the only
check that catches a removed coalescing guard: the browser burst test passes on the 350 ms debounce alone.
It is source-driven, not a browser or disk test; tests/test_2i_adversarial_saves.py covers the browser.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required to run the write-amplification probe")
def test_forty_edit_burst_coalesces_to_at_most_three_record_writes():
    result = subprocess.run(
        ["node", str(ROOT / "tools" / "2i_write_amplification_probe.cjs")],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: burst coalesced without losing latest manuscript" in result.stdout
