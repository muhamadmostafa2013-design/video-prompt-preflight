"""Protect CLI automation when Windows pipes start with a legacy code page."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _invoke(*args):
    env = dict(os.environ, PYTHONIOENCODING="cp1252:strict")
    return subprocess.run(
        [sys.executable, "-m", "vpp.cli", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=False,
        timeout=20,
    )


def test_blocked_scene_writes_valid_utf8_json_to_redirected_stdout():
    result = _invoke("lint", "examples/bad_scene.yml", "--json")
    assert result.returncode == 2
    assert result.stderr == b""
    report = json.loads(result.stdout.decode("utf-8"))
    assert report["passed"] is False
    assert any("\u0645" in finding["message"] for finding in report["findings"])


def test_missing_unicode_input_writes_utf8_diagnostic_to_redirected_stderr(tmp_path):
    filename = "\u0627\u0644\u062f\u0631\u0633-\u00e4-\U0001f3b5.yml"
    result = _invoke("lint", str(tmp_path / filename), "--json")
    assert result.returncode == 2
    assert result.stdout == b""
    message = result.stderr.decode("utf-8")
    assert "VPP input error" in message
    assert filename in message
    assert "Traceback" not in message
