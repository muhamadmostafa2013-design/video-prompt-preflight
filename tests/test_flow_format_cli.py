import json
import subprocess
import sys

import pytest

TARGET = "flow-veo-3.1-lite-text-to-video"


def lint(tmp_path, scene, target=True):
    spec = tmp_path / "scene.json"
    spec.write_text(json.dumps(scene), encoding="utf-8")
    args = ["--target", TARGET] if target else []
    process = subprocess.run(
        [sys.executable, "-m", "vpp.cli", "lint", str(spec), "--json", *args],
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=15,
    )
    assert not process.stderr
    return process.returncode, json.loads(process.stdout)


@pytest.mark.parametrize("duration", [4, 6, 8.0])
@pytest.mark.parametrize("aspect", ["9:16", "16:9"])
def test_supported_formats(tmp_path, duration, aspect):
    code, report = lint(tmp_path, {"duration_seconds": duration, "aspect_ratio": aspect})
    assert code == 0
    assert report["passed"] and report["risk_score"] == 0
    assert [item["rule_id"] for item in report["findings"]] == ["preflight.clean"]


def test_generic_lint_remains_unchanged(tmp_path):
    scene = {"duration_seconds": 10, "aspect_ratio": "9:16"}
    code, report = lint(tmp_path, scene, target=False)
    assert code == 0
    assert report["passed"] and report["risk_score"] == 0
    assert [item["rule_id"] for item in report["findings"]] == ["preflight.clean"]
    code, report = lint(tmp_path, scene)
    assert code == 2
    assert not report["passed"]
    assert [item["rule_id"] for item in report["findings"]] == ["target.flow_veo_lite.duration"]


@pytest.mark.parametrize("aspect", ["1:1", None, ["9:16"]])
def test_unsupported_or_missing_ratio(tmp_path, aspect):
    code, report = lint(tmp_path, {"duration_seconds": 8, "aspect_ratio": aspect})
    assert code == 2
    assert [item["rule_id"] for item in report["findings"]] == ["target.flow_veo_lite.aspect_ratio"]


def test_import_defaults_do_not_count_as_explicit(tmp_path):
    code, report = lint(tmp_path, {
        "duration_seconds": 8, "aspect_ratio": "9:16",
        "parse_meta": {"duration_explicit": False, "aspect_explicit": False},
    })
    assert code == 2
    assert {item["rule_id"] for item in report["findings"]} == {
        "target.flow_veo_lite.duration", "target.flow_veo_lite.aspect_ratio",
    }


def test_target_does_not_hide_generic_scene_errors(tmp_path):
    code, report = lint(tmp_path, {"duration_seconds": 8, "aspect_ratio": "9:16", "rules": []})
    assert code == 2
    assert [item["rule_id"] for item in report["findings"]] == ["rules.type"]
