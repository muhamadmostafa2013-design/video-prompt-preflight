import json
import shutil
import subprocess

import pytest

import vpp.studio_review as studio
from vpp.song_alignment import _hash
from vpp.waveform import waveform


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_waveform_real_encoded_audio_and_silence(tmp_path):
    source = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", "-c:a", "pcm_s16le", str(source)], check=True)
    result = waveform(source, bins=64)
    assert len(result["peaks"]) == 64
    assert all(0 < p <= 1 for p in result["peaks"])
    assert result["video_sha256"] == _hash(source)
    assert result["decoded_audio_seconds"] == pytest.approx(1)
    assert not result["publication_approved"]
    silence = tmp_path / "silence.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=8000:cl=mono", "-t", "1", str(silence)], check=True)
    assert not any(waveform(silence, bins=64)["peaks"])


def test_desktop_review_blocks_when_models_missing(tmp_path, monkeypatch):
    video = tmp_path / "video"
    lyrics = tmp_path / "lyrics"
    srt = tmp_path / "source.srt"
    video.write_bytes(b"fixture")
    lyrics.write_text("Ein Nomen")
    srt.write_text("1\n00:00:00,100 --> 00:00:00,500\nEin Nomen\n")
    model = tmp_path / "models"
    model.mkdir()
    monkeypatch.setattr(studio, "waveform", lambda _: {"peaks": [0.1]})
    monkeypatch.setattr(studio, "visual_scan", lambda _: {"decision": "review"})
    monkeypatch.setattr(studio, "run_alignment", lambda _: 2)

    def missing(_):
        raise RuntimeError("model unavailable")
    monkeypatch.setattr(studio, "LocalGermanCTC", missing)
    output = tmp_path / "result"
    report = studio.run_desktop_review(video, lyrics, srt, model, model, model, output)
    assert report["decision"] == "blocked"
    assert report["stages"]["whisperx"]["status"] == "failed"
    assert report["stages"]["ctc"]["status"] == "failed"
    assert report["stages"]["consensus_repair"]["status"] == "blocked"
    assert not (output / "caption-review" / "REVIEW_ONLY.srt").exists()
    assert json.loads((output / "project-report.json").read_text()) == report
    assert not report["publication_approved"]
