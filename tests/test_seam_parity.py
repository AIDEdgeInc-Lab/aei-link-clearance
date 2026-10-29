"""Python/JS parity for results computed from provider heights. The JS half needs node and a Map checkout (MAP_REPO); without them it is
SKIPPED -- say so in the release record, it is not a pass."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP = Path(os.environ.get("MAP_REPO", Path.home() / "velorona-repos" / "aei-link-clearance"))


def test_committed_fixture_matches_what_python_computes_now():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "fixtures" / "make_seam_parity.py"), "--check"],
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True)
    assert r.returncode == 0, "seam_parity.json is stale: run tests/fixtures/make_seam_parity.py and review the diff"


@pytest.mark.skipif(not shutil.which("node") or not (MAP / "web" / "linkmath.js").exists(), reason="needs node and a Map checkout (MAP_REPO)")
def test_map_js_agrees_with_python_for_provider_heights():
    r = subprocess.run(["node", str(ROOT / "parity" / "seam_parity.mjs")], env={**os.environ, "MAP_REPO": str(MAP)}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
