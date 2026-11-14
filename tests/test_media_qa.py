"""Offline media QA contract tests. Optional binaries/models are mocked deliberately."""
import shutil
import subprocess

import pytest

from vpp import media_qa
from vpp.cli import build_parser, cmd_check_video

META = {"duration_seconds": 10.0, "width": 1080, "height": 1920,
        "aspect_ratio": 1080 / 1920, "has_audio": True}
SCENE = {"duration_seconds": 10, "aspect_ratio": "9:16",
         "screen_text": ["laufen", "sich verlaufen"],
         "spoken": {"arabic": "اشرح الفكرة", "german_by_presenter": []}}


def test_metadata_only_passes_without_external_dependencies(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: dict(META))
    result = media_qa.inspect_video("any.mp4")
    assert result["decision"] == "pass"
    assert result["checks"] == []


def test_missing_content_evidence_requires_review(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: dict(META))
    result = media_qa.inspect_video("any.mp4", SCENE)
    assert result["decision"] == "review"
    assert {x["name"] for x in result["checks"]} >= {"exact_screen_text", "speech_transcript"}


def test_duration_or_aspect_failure_blocks_release(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video",
                        lambda _: {**META, "duration_seconds": 12, "aspect_ratio": 1.78})
    result = media_qa.inspect_video("any.mp4", SCENE)
    assert result["decision"] == "fail"
    assert sum(x["status"] == "fail" for x in result["checks"]) == 2


def test_sampled_ocr_is_advisory_even_when_text_observed(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: dict(META))
    monkeypatch.setattr(media_qa, "sample_frames",
                        lambda path, duration, count, directory: [{"seconds": 5, "path": "sample"}])
    monkeypatch.setattr(media_qa, "ocr_frames",
                        lambda frames, lang: [{"seconds": 5, "text": "LAUFEN\nsich verlaufen"}])
    result = media_qa.inspect_video("any.mp4", SCENE, ocr=True)
    assert result["decision"] == "review"
    assert all(x["status"] == "observed" for x in result["checks"] if x["name"] == "exact_screen_text")


def test_ocr_missing_word_not_mislabeled_success(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: dict(META))
    monkeypatch.setattr(media_qa, "sample_frames",
                        lambda path, duration, count, directory: [{"seconds": 3, "path": "sample"}])
    monkeypatch.setattr(media_qa, "ocr_frames",
                        lambda frames, lang: [{"seconds": 3, "text": "laufen"}])
    result = media_qa.inspect_video("any.mp4", SCENE, ocr=True)
    assert result["decision"] == "review"
    assert any(x["status"] == "review" and x["expected"] == "sich verlaufen"
               for x in result["checks"])


def test_no_audio_stream_is_failing_when_asr_requested(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: {**META, "has_audio": False})
    result = media_qa.inspect_video("any.mp4", SCENE, asr_model="/local/model")
    assert result["decision"] == "fail"
    assert any(x["name"] == "audio" and x["status"] == "fail" for x in result["checks"])


def test_refuses_remote_model_identifier():
    with pytest.raises(media_qa.MediaQAError, match="LOCAL model"):
        media_qa.transcript_local("video.mp4", "small")


def test_rejects_bad_frame_count():
    with pytest.raises(media_qa.MediaQAError, match="Frame count"):
        media_qa.sample_frames("video.mp4", 10, 0, "/tmp")


def test_invalid_aspect_fails_closed(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: dict(META))
    with pytest.raises(media_qa.MediaQAError, match="aspect"):
        media_qa.inspect_video("any.mp4", {"aspect_ratio": "0:9"})


def test_cli_parser_exposes_media_qa_flags():
    args = build_parser().parse_args(
        ["check-video", "a.mp4", "--spec", "scene.yml", "--ocr",
         "--ocr-lang", "deu+eng", "--frames", "8", "--json"])
    assert args.func is cmd_check_video
    assert args.ocr and args.ocr_lang == "deu+eng"
    assert args.frames == 8


def test_normalization_handles_unicode_and_whitespace():
    assert media_qa._norm("SICH  VERLAUFEN") == media_qa._norm("sich verlaufen")
    assert media_qa._norm("für") == "für"


def test_missing_video_fails_safely():
    with pytest.raises(media_qa.MediaQAError, match="does not exist"):
        media_qa.probe_video("/nonexistent-vpp-test.mp4")

@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="ffmpeg and ffprobe are optional system binaries")
def test_real_video_metadata_probe_and_gate(tmp_path):
    video = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "color=c=black:s=360x640:r=10:d=1", "-t", "1",
         "-c:v", "mpeg4", str(video)], check=True, timeout=35,
    )
    metadata = media_qa.probe_video(video)
    assert metadata["width"] == 360
    assert metadata["height"] == 640
    assert metadata["has_audio"] is False
    good = media_qa.inspect_video(
        video, {"duration_seconds": 1, "aspect_ratio": "9:16"}
    )
    assert good["decision"] == "pass"
    wrong = media_qa.inspect_video(video, {"duration_seconds": 3})
    assert wrong["decision"] == "fail"

def test_missing_speech_audio_fails_even_without_asr(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: {**META, "has_audio": False})
    report = media_qa.inspect_video("any.mp4", SCENE)
    assert report["decision"] == "fail"
    assert any(x["name"] == "expected_speech_audio" for x in report["checks"])


def test_ocr_does_not_match_word_inside_another_word(monkeypatch):
    monkeypatch.setattr(media_qa, "probe_video", lambda _: dict(META))
    monkeypatch.setattr(media_qa, "sample_frames",
                        lambda path, duration, count, directory: [{"seconds": 3, "path": "sample"}])
    monkeypatch.setattr(media_qa, "ocr_frames",
                        lambda frames, lang: [{"seconds": 3, "text": "auflaufen"}])
    output = media_qa.inspect_video("any.mp4", {"screen_text": ["laufen"]}, ocr=True)
    assert output["checks"][0]["status"] == "review"
