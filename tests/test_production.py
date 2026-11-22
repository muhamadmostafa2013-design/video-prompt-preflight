"""Production security and offline regression tests; no Gemini API calls."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from vpp import production as p

ROOT = Path(__file__).resolve().parents[1]


def valid_video():
    return {"type": "video", "title": "Campus",
            "aspect_ratio": "9:16",
            "learning_objective": "Students can greet each other politely in German.",
            "cefr_level": "A1", "learner_age": [16, 25],
            "target_phrases": ["Guten Morgen!"],
            "scenes": [{"duration_seconds": 8,
                        "prompt": 'Student A says "Guten Morgen!" clearly to another student on campus.',
                        "expected_dialogue": [{"speaker": "Student A", "text": "Guten Morgen!"}]}]}


def test_load_real_video_job():
    job = p.validate_job(p._yaml(ROOT / "examples/production_university_video.yml"), ROOT)
    assert len(job["scenes"]) == 2
    assert job["aspect_ratio"] == "9:16"
    assert p.estimated_usd(job) == 1.28


def test_load_real_song_job():
    job = p.validate_job(p._yaml(ROOT / "examples/production_animals_song.yml"), ROOT)
    report = p.preflight(job)
    assert report["qa"]["passed"]
    assert "der Hund" in report["prompts"][0]
    assert p.estimated_usd(job) == 0.10


@pytest.mark.parametrize("change", [
    {"type": "unknown"},
    {"scenes": []},
    {"scenes": [{"duration_seconds": 16, "prompt": "A long enough prompt about speech."}]},
    {"scenes": [{"duration_seconds": 2, "prompt": "A long enough prompt about speech."}]},
    {"scenes": [{"duration_seconds": 8, "prompt": "too short"}]},
    {"aspect_ratio": "4:3"},
    {"scenes": [{"duration_seconds": True, "prompt": "A long enough prompt about speech."}]},
])
def test_reject_invalid_video_jobs(change):
    job = valid_video()
    job.update(change)
    with pytest.raises(p.ProductionError):
        p.validate_job(job, ROOT)


def test_reject_traversal(tmp_path):
    with pytest.raises(p.ProductionError):
        p.validate_job({"type": "song", "song_spec": "../secret.yml"}, tmp_path)


def test_paid_gate_requires_secret_and_explicit_approval():
    with pytest.raises(p.ProductionError):
        p.paid_gate(0.5, 2.0, {"GEMINI_API_KEY": "dummy"})
    with pytest.raises(p.ProductionError):
        p.paid_gate(0.5, 2.0, {"VPP_ALLOW_PAID_GENERATION": "YES"})
    with pytest.raises(p.ProductionError):
        p.paid_gate(1.6, 1.0, {"VPP_ALLOW_PAID_GENERATION": "YES",
                                "GEMINI_API_KEY": "dummy"})
    p.paid_gate(0.5, 2.0, {"VPP_ALLOW_PAID_GENERATION": "YES",
                             "GEMINI_API_KEY": "dummy"})


@pytest.mark.parametrize("bad_limit", [0, -2, 26, float("inf"), float("nan")])
def test_invalid_limits_are_rejected(bad_limit):
    with pytest.raises(p.ProductionError):
        p.paid_gate(0.1, bad_limit, {"VPP_ALLOW_PAID_GENERATION": "YES",
                                       "GEMINI_API_KEY": "dummy"})


def test_dry_run_never_calls_gemini(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "triple_review",
                        lambda text, provider: {"passed": True, "confidence_band": "medium",
                                                "heuristic_score": 82})
    monkeypatch.setattr(p, "generate_paid", lambda *args: pytest.fail("Called API in dry-run!"))
    out = tmp_path / "output"
    result = p.produce(ROOT / "examples/production_university_video.yml", ROOT, out)
    assert result["mode"] == "dry-run"
    assert not (out / "final.mp4").exists()
    assert json.loads((out / "preflight.json").read_text())["human_review_required"]
    assert "Entschuldigung" in (out / "prompts.txt").read_text(encoding="utf-8")


def test_production_paid_gate_before_any_output_or_network(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "triple_review", lambda *_args, **_kwargs: {"passed": True})
    monkeypatch.setattr(p, "generate_paid", lambda *_args: pytest.fail("API reached"))
    out = tmp_path / "paid"
    with pytest.raises(p.ProductionError, match="approval"):
        p.produce(ROOT / "examples/production_university_video.yml", ROOT, out,
                  mode="paid", environ={"GEMINI_API_KEY": "dummy"})
    assert not out.exists()


def test_triple_review_gate_is_not_bypassed(monkeypatch):
    job = p.validate_job(valid_video(), ROOT)
    monkeypatch.setattr(p, "triple_review", lambda *_args, **_kwargs: {"passed": False})
    with pytest.raises(p.ProductionError, match="Triple Verify"):
        p.preflight(job)


def test_model_identifiers_are_fixed():
    assert p.VIDEO_MODEL == "gemini-omni-1.2-flash"
    assert p.MUSIC_MODEL == "lyria-3.5"


def test_decode_invalid_payload_is_blocked():
    with pytest.raises(p.ProductionError):
        p._decode("not base64!!")


def test_paid_model_stub_uses_expected_schema(tmp_path, monkeypatch):
    calls = []
    encoded = "QUJDRA=="  # Small synthetic payload; no FFprobe or real media.
    class Interactions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if kwargs["model"] == p.VIDEO_MODEL:
                return SimpleNamespace(output_video=SimpleNamespace(data=encoded))
            return SimpleNamespace(output_audio=SimpleNamespace(data=encoded),
                                   output_text="Unverified transcription")
    monkeypatch.setattr(p, "generate_paid", p.generate_paid)
    # If the code path still imports google-genai internally, inject an isolated stub.
    import sys
    fake_genai = SimpleNamespace(Client=lambda api_key: SimpleNamespace(interactions=Interactions()))
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    job = p.validate_job(valid_video(), ROOT)
    paths = p.generate_paid(job, ["A complete video scene."], tmp_path, "dummy")
    assert len(paths) == 1 and paths[0].read_bytes() == b"ABCD"
    assert calls[0]["model"] == p.VIDEO_MODEL
    assert calls[0]["response_format"]["duration"] == "8s"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="FFmpeg unavailable on this runner")
def test_offline_demo_renders_real_mp4(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "triple_review", lambda *_args, **_kwargs: {"passed": True})
    root = tmp_path
    spec = root / "job.yml"
    import yaml
    spec.write_text(yaml.safe_dump(valid_video()), encoding="utf-8")
    result = p.produce(spec, root, root / "out", mode="demo")
    assert result["output"] == "final.mp4"
    assert (root / "out/final.mp4").stat().st_size > 10_000


def test_unmocked_vpp_review_for_real_university_example():
    job = p.validate_job(p._yaml(ROOT / "examples/production_university_video.yml"), ROOT)
    result = p.preflight(job)
    assert len(result["prompts"]) == 2
    assert len(result["qa"]) == 2
    assert all(x["passed"] for x in result["qa"])
