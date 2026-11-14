"""Ten independent end-to-end / boundary acceptance gates for the local product.

Run: pytest -vv tests/test_release_acceptance.py
All ten must pass. Unit regressions run separately in standard test.yml.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from vpp import __version__
from vpp.media_qa import MediaQAError, inspect_video, ocr_frames, probe_video, transcript_local
from vpp.optimizer import optimize_prompt
from vpp.prompt_analyzer import analyze_prompt
from vpp.triple_review import triple_review

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT / "examples/ver_scene_1_prompt.txt").read_text(encoding="utf-8")
BAD = (ROOT / "examples/conflicting_prompt.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def real_video(tmp_path_factory):
    """Generate a genuine 2-second video on the runner, not a fake metadata object."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe unavailable in generic matrix; dedicated release workflow installs them.")
    output = tmp_path_factory.mktemp("release-video") / "two-seconds.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "color=c=blue:s=640x360:r=10:d=2", "-t", "2",
         "-c:v", "mpeg4", str(output)],
        check=True, capture_output=True, text=True, timeout=45,
    )
    return output


def test_gate_01_version_contract_consistent():
    version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert version_file == __version__
    assert re.search(r'^version = "' + re.escape(__version__) + r'"$', manifest, re.M)
    assert triple_review(PROMPT, provider="veo")["version"] == __version__


def test_gate_02_valid_prompt_accepts_and_keeps_words():
    scene, report = analyze_prompt(PROMPT)
    assert report.passed
    assert scene["duration_seconds"] == 10
    assert {"ver-", "laufen", "sich verlaufen"} <= set(scene["screen_text"])


def test_gate_03_conflicting_prompt_is_rejected():
    _, report = analyze_prompt(BAD)
    rules = {f.rule_id for f in report.findings}
    assert not report.passed
    assert {"prompt.duration.conflict", "prompt.music.conflict",
            "prompt.subtitle.conflict", "prompt.audio.conflict"} <= rules


def test_gate_04_optimizer_preserves_hard_requirements():
    result = optimize_prompt(PROMPT)
    output = result["optimized_prompt"]
    assert "sich verlaufen" in output
    assert "no Arabic text on screen" in output
    assert "no automatic subtitles" in output
    assert result["after"]["risk_score"] <= result["before"]["risk_score"]


def test_gate_05_three_round_review_is_stable():
    result = triple_review(PROMPT, provider="veo")
    assert result["passed"]
    assert [r["round"] for r in result["rounds"]] == [1, 2, 3]
    assert result["final_prompt"]


def test_gate_06_actual_video_probe_passes(real_video):
    metadata = probe_video(real_video)
    assert (metadata["width"], metadata["height"]) == (640, 360)
    assert metadata["has_audio"] is False
    assert abs(metadata["duration_seconds"] - 2) < .2
    report = inspect_video(real_video, {"duration_seconds": 2, "aspect_ratio": "16:9"})
    assert report["decision"] == "pass"


def test_gate_07_actual_video_wrong_spec_fails(real_video):
    result = inspect_video(real_video, {"duration_seconds": 8, "aspect_ratio": "9:16"})
    assert result["decision"] == "fail"
    assert {c["name"] for c in result["checks"] if c["status"] == "fail"} == {
        "duration", "aspect_ratio"
    }


def test_gate_08_requested_speech_without_audio_fails(real_video):
    scene = {"spoken": {"arabic": "أهلا بكم", "german_by_presenter": []}}
    result = inspect_video(real_video, scene)
    assert result["decision"] == "fail"
    assert any(c["name"] == "expected_speech_audio" for c in result["checks"])


def test_gate_09_real_local_ocr_is_advisory(real_video, tmp_path, monkeypatch):
    from PIL import Image, ImageDraw, ImageFont

    image_path = tmp_path / "readable.png"
    image = Image.new("RGB", (900, 180), color="white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not Path(font_path).exists():
        pytest.fail("Ubuntu release runner must provide DejaVuSans.ttf.")
    font = ImageFont.truetype(font_path, 82)
    draw.text((18, 40), "HELLO VIDEO", fill="black", font=font)
    image.save(image_path)

    text = ocr_frames([{"seconds": 1, "path": image_path}], "eng")[0]["text"]
    assert "HELLO VIDEO" in text.upper()

    import vpp.media_qa as qa
    monkeypatch.setattr(qa, "sample_frames", lambda *args: [{"seconds": 1, "path": image_path}])
    report = inspect_video(real_video, {"screen_text": ["HELLO VIDEO"]}, ocr=True)
    assert report["decision"] == "review"
    assert report["checks"][0]["status"] == "observed"


def test_gate_10_security_and_no_auto_remote_asr():
    ui = (ROOT / "web/ui.js").read_text(encoding="utf-8")
    old_ui = (ROOT / "web/app.js").read_text(encoding="utf-8")
    assert "escapeHtml(x.observed)" in ui and "escapeHtml(x.expected)" in ui
    assert "escapeHtml(f.message)" in ui and "safeEvidenceUrl(s.url)" in ui
    assert "escapeHtml(f.message)" in old_ui
    with pytest.raises(MediaQAError, match="LOCAL model"):
        transcript_local("/does-not-exist.mp4", "a-remote-whisper-model")
