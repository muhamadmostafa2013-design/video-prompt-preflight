"""Adversarial cross-component regression coverage."""
import json

import pytest

from vpp.consensus import compare_tracks
from vpp.integration_audit import simulate_integration
from vpp.intelligence_planning import cost_plan
from vpp.intelligence_workflow import write_dashboard
from vpp.model_evidence import rank_scene
from vpp.quality_evidence import _read_json


@pytest.mark.parametrize("seed", [17, 20261124, 31337])
def test_cross_component_simulation(seed):
    report = simulate_integration(seed, 1200)
    assert report["failed_trials"] == 0, report["failures"]
    assert len(report["counts"]) == 12
    assert not report["publication_approved"]


@pytest.mark.parametrize("bad", ['{"a": 1, "a": 2}', '{"x": NaN}', '{"x": Infinity}'])
def test_reject_ambiguous_json(tmp_path, bad):
    path = tmp_path / "data.json"
    path.write_text(bad)
    with pytest.raises(ValueError):
        _read_json(path)


def test_duration_gate_does_not_allow_small_out_of_bounds_agreement():
    digest = "a"*64
    a = {"backend": "whisperx", "family": "whisper", "model": "a", "audio_sha256": digest,
         "words": [{"word": "Ein", "start": .5, "end": 1}]}
    b = {**a, "backend": "wav2vec2-ctc", "family": "wav2vec2",
         "words": [{"word": "Ein", "start": .5, "end": 1.01}]}
    assert compare_tracks([a, b], digest, duration=1)["decision"] == "blocked"


def test_unknown_cost_is_not_reported_as_avoided():
    plan = cost_plan([{"id": "a", "status": "unknown", "regenerate_cents": 10}], 0)
    assert plan["potential_avoided_cents"] is None


def test_invalid_cosine_is_not_a_valid_signal():
    with pytest.raises(ValueError):
        rank_scene(["street", "office"], [2.0, .1])


def test_dashboard_handles_null_metrics_and_escapes(tmp_path):
    path = tmp_path / "dashboard.html"
    write_dashboard({"decision": "review", "agreement": None, "before": {"metrics": None},
                     "stages": {"bad": "</details><script>bad()</script>"}}, path)
    text = path.read_text()
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "Evidence details" in text


def test_json_report_nonfinite_never_rendered(tmp_path):
    path = tmp_path / "report.html"
    with pytest.raises(ValueError):
        write_dashboard({"decision": "review", "bad": float("nan")}, path)
    assert not path.exists()


def test_report_keeps_valid_unicode(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"de": "grüßen", "ar": "أهلاً"}, ensure_ascii=False), encoding="utf-8")
    assert _read_json(path)["de"] == "grüßen"
