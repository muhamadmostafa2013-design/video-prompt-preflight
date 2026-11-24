"""Regression and real encoded-media smoke checks for post-production QA."""
import json
import shutil
import subprocess

import pytest

from vpp.project_quality import run_project
from vpp.quality_engine import (
    language_review,
    model_readiness,
    render_draft,
    simulate_faults,
    visual_scan,
)
from vpp.song_alignment import _hash
from vpp.subtitle_sync import parse_srt


@pytest.mark.parametrize("seed", [20261124, 19, 721])
def test_seeded_fault_injection(seed):
    result = simulate_faults(seed, 600)
    assert result["trials"] == 600
    assert result["failed_trials"] == 0
    assert sum(result["fault_counts"].values()) == 600
    assert not result["publication_approved"]


def test_language_glossary_only():
    captions = parse_srt("1\n00:00:01,000 --> 00:00:02,000\nEine Frage stellen\nسؤال")
    report = language_review(captions, {"eine Frage stellen": ["طرح سؤال"]})
    assert report["issues"][0]["code"] == "glossary_translation_review"
    assert not report["publication_approved"]


def test_model_readiness_never_calls_paid():
    result = model_readiness()
    assert result["remote_fallback"] is False
    assert result["model_weights_verified"] is False


@pytest.fixture
def encoded_fixture(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg required; release acceptance workflow installs it.")
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=blue:s=320x240:r=25:d=4", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=4",
                    "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(source)],
                   check=True, capture_output=True, timeout=30)
    lyrics = tmp_path / "de.txt"
    lyrics.write_text("Ein Nomen", encoding="utf-8")
    srt = tmp_path / "old.srt"
    srt.write_text("1\n00:00:01,500 --> 00:00:02,500\nEin Nomen\nاسم\n", encoding="utf-8")
    run = tmp_path / "align"
    (run / "asr").mkdir(parents=True)
    raw = run / "asr" / "vocals.json"
    raw.write_text(json.dumps({"word_segments": [
        {"word": "Ein", "start": .8, "end": 1.0, "score": .9},
        {"word": "Nomen", "start": 1.0, "end": 1.4, "score": .9}]}))
    (run / "alignment_report.json").write_text(json.dumps({
        "decision": "review", "evidence_schema": "vpp.whisperx.words.v1",
        "audio_sha256": _hash(source), "reference_sha256": _hash(lyrics),
        "word_evidence_sha256": _hash(raw), "duration_seconds": 4, "min_score": .5,
    }))
    return source, lyrics, srt, run


def test_real_mux_with_synthetic_acoustic_evidence(encoded_fixture, tmp_path):
    source, lyrics, srt, run = encoded_fixture
    before = _hash(source)
    result = render_draft(source, source, lyrics, srt, run, tmp_path / "output", clean_source=True)
    assert result["audio_packets_and_timeline_preserved"]
    assert result["video_packets_and_timeline_preserved"]
    assert result["embedded_subtitle_roundtrip_verified"]
    assert result["post_repair_metrics"]["max_absolute_ms"] == 0
    assert _hash(source) == before
    assert not result["publication_approved"]


def test_real_visual_decode(encoded_fixture):
    source, *_ = encoded_fixture
    result = visual_scan(source)
    assert result["full_video_decode"] == "completed"
    assert result["samples"] == 4
    assert any(a["code"] == "near_identical_samples" for a in result["alerts"])


def test_require_clean_source(encoded_fixture, tmp_path):
    source, lyrics, srt, run = encoded_fixture
    with pytest.raises(ValueError, match="burned-in"):
        render_draft(source, source, lyrics, srt, run, tmp_path / "output", clean_source=False)


def test_actual_burned_draft(encoded_fixture, tmp_path):
    source, lyrics, srt, run = encoded_fixture
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], check=True,
                             capture_output=True, text=True, timeout=20).stdout
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], check=True,
                              capture_output=True, text=True, timeout=20).stdout
    if " subtitles " not in filters or "libx264" not in encoders:
        pytest.skip("FFmpeg needs libass subtitles and libx264.")
    result = render_draft(source, source, lyrics, srt, run, tmp_path / "burn",
                          clean_source=True, burn=True)
    assert result["mode"] == "burned_draft"
    assert result["audio_packets_and_timeline_preserved"]
    assert result["full_audio_decode"] == "completed"
    assert not result["video_packets_and_timeline_preserved"]
    assert not result["publication_approved"]
    assert (tmp_path / "burn" / "DRAFT_REQUIRES_HUMAN_REVIEW.mp4").is_file()


def test_unrelated_audio_refused(encoded_fixture, tmp_path):
    source, lyrics, srt, run = encoded_fixture
    other = tmp_path / "different.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=800:sample_rate=48000:duration=4", str(other)],
                   check=True, capture_output=True, timeout=20)
    with pytest.raises(ValueError, match="audio differs"):
        render_draft(source, other, lyrics, srt, run, tmp_path / "bad", clean_source=True)
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("fault", [None, "wrong_source", "scene_conflict"])
def test_encoded_project_pipeline(encoded_fixture, tmp_path, monkeypatch, fault):
    """Real decoding, consensus, SRT repair and MP4 mux; fixture model evidence."""
    source, lyrics, srt, alignment = encoded_fixture
    before = _hash(source)
    old = srt.read_bytes()
    digest = "0"*64 if fault == "wrong_source" else before
    track = tmp_path / "track.json"
    track.write_text(json.dumps({"backend": "wav2vec2-ctc", "family": "wav2vec2",
        "model": "synthetic-fixture", "audio_sha256": digest, "words": [
            {"word": "Ein", "start": .8, "end": 1.0},
            {"word": "Nomen", "start": 1.0, "end": 1.4}]}))
    (tmp_path / "clip").mkdir()
    scenes = tmp_path / "scenes.json"
    scenes.write_text(json.dumps([{"id": "a", "start": 0, "end": 4,
        "expected": "blue frame", "alternatives": ["red frame"],
        "required_phrases": ["Ein Verb" if fault == "scene_conflict" else "Ein Nomen"]}]))
    monkeypatch.setattr("vpp.project_quality.semantic_scan",
                        lambda *args: {"decision": "review",
                            "samples": [{"signal": "supports_expected"}]})
    manifest = tmp_path / "project.json"
    manifest.write_text(json.dumps({"audio": source.name, "video": source.name,
        "lyrics": lyrics.name, "srt": srt.name, "alignment_run": alignment.name,
        "clip_model": "clip", "scene_manifest": scenes.name, "independent_tracks": [track.name],
        "render": True, "clean_source": True}))
    output = tmp_path / "project-output"
    report = run_project(manifest, output)
    assert not report["publication_approved"]
    assert _hash(source) == before and srt.read_bytes() == old
    assert (output / "dashboard.html").is_file()
    target = output / "video-review" / "DRAFT_REQUIRES_HUMAN_REVIEW.mp4"
    if fault:
        assert report["decision"] == "blocked"
        assert not target.exists()
    else:
        assert report["decision"] == "review"
        assert target.is_file()
        rendered = report["stages"]["render"]["evidence"]
        assert rendered["audio_packets_and_timeline_preserved"]
        assert rendered["embedded_subtitle_roundtrip_verified"]
        assert rendered["post_repair_metrics"]["max_absolute_ms"] == 0
