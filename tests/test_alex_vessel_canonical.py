"""The committed PubPartner Alex vessel must always be the canonical blob (CLAUDE.md).

tests/test_saves_survive_restart.py guards the file on disk during a test run; this guards what Git holds, so a
commit that replaced or removed the vessel on any machine is caught by the next test run anywhere.
The pre-commit guard in tools/git-hooks/pre-commit stops such a commit before it is made.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VESSEL = "data/pubpartner/vessels/alex.pubpartner"
CANONICAL = "96fa66a728d07d5ff43b0d3d7fc17a466765cec1"


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="not a Git checkout")
def test_committed_alex_vessel_is_the_canonical_blob():
    result = subprocess.run(["git", "rev-parse", "HEAD:" + VESSEL], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, "the Alex vessel is missing from the latest commit: " + result.stderr
    assert result.stdout.strip() == CANONICAL, "the committed Alex vessel is not the canonical blob"
