"""Reproductions from Claude's independent audit; never replace evidence with text assertions."""
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest

from vpp.compiler import compile_scene
from vpp.failure_memory import load_failure_memory
from vpp.jev_judge import jev_review
from vpp.media_qa import probe_video
from vpp.optimizer import optimize_prompt
from vpp.parser import parse_prompt
from vpp.prompt_analyzer import analyze_prompt


def test_negated_use_music_not_a_conflict():
    _, report = analyze_prompt("Create a 10 second 9:16 video. Do not use background music.")
    assert "prompt.music.conflict" not in {f.rule_id for f in report.findings}


def test_piano_music_alone_does_not_imply_add_music():
    _, report = analyze_prompt("Create a 10 second 9:16 video. No music. The piano music is a forbidden concept.")
    assert "prompt.music.conflict" not in {f.rule_id for f in report.findings}


def test_true_music_contradiction_still_blocks():
    _, report = analyze_prompt("Create a 10 second 9:16 video. No background music. Add subtle background music.")
    assert "prompt.music.conflict" in {f.rule_id for f in report.findings}


def test_hold_seconds_are_not_global_duration_conflicts():
    text = "Create a 10-second 9:16 video. Hold for 2 seconds. Then reveal text."
    scene, report = analyze_prompt(text)
    assert scene["duration_seconds"] == 10
    assert scene["parse_meta"]["duration_mentions"] == [10]
    assert "prompt.duration.conflict" not in {f.rule_id for f in report.findings}


def test_global_duration_chosen_not_hold_duration():
    scene = parse_prompt("Hold for 2 seconds. Create a 10 second scene in 9:16.")
    assert scene["duration_seconds"] == 10


def test_range_seconds_parsed_with_real_absolute_time():
    scene = parse_prompt("Create a 10 second video. TIMELINE:\n0-3 seconds show hook\n7-9s show closer")
    assert scene["timeline"] == [
        {"start": 0.0, "end": 3.0, "seconds": 3.0, "action": "show hook"},
        {"start": 7.0, "end": 9.0, "seconds": 2.0, "action": "show closer"},
    ]


def test_compiler_does_not_destroy_gaps():
    scene = parse_prompt("Create a 10 second 9:16 video.\nTIMELINE:\n3-5s show camera\n7-9s show scenery")
    output = compile_scene(scene)
    assert "3-5s show camera" in output
    assert "7-9s show scenery" in output
    assert "0-2s show camera" not in output


def test_camera_motion_not_rewritten_as_static_screen_text():
    scene = parse_prompt(
        "Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\n"
        "TIMELINE:\n0-5s animate the camera to the presenter\n5-10s show laufen"
    )
    output = compile_scene(scene)
    assert "animate the camera to the presenter" in output
    assert "show the camera as static text" not in output


def test_actual_exact_text_morph_remains_guarded():
    scene = parse_prompt(
        "Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nsich verlaufen\n"
        "TIMELINE:\n0-10s transform laufen into sich verlaufen"
    )
    output = compile_scene(scene)
    assert "hard cut" in output and "do not morph" in output


def test_arabic_musical_conflict_is_not_clean():
    _, report = analyze_prompt("فيديو لمدة 10 ثواني بدون موسيقى وضيف موسيقى")
    assert "prompt.music.conflict.ar" in {f.rule_id for f in report.findings}
    assert not report.passed


def test_arabic_only_without_duration_requests_review():
    _, report = analyze_prompt("اعمل فيديو فيه ألوان جميلة")
    ids = {f.rule_id for f in report.findings}
    assert "prompt.duration.inferred" in ids
    assert "prompt.arabic.limited" in ids


def test_jev_cannot_override_failing_local_preflight():
    from vpp.triple_review import triple_review

    bad = "Create a 10 second video but make it 12 seconds long. No music. Add background music."
    local = triple_review(bad, provider="veo")
    assert local["passed"] is False
    client = Mock()
    result = jev_review(local, original_prompt=bad, client=client)
    assert result["decision"] == "block"
    assert result["semantic_gate"]["decision"]["decision"] == "block"
    client.system_one.assert_not_called()


def test_failure_memory_present_as_package_resource():
    records = load_failure_memory()
    assert len(records) >= 3
    assert {"failure-0001", "failure-0002", "failure-0003"} <= {
        r["id"] for r in records
    }


def test_check_video_cli_with_no_spec_needs_human_review(monkeypatch):
    from vpp import cli
    monkeypatch.setattr(cli, "inspect_video", lambda *args, **kwargs: {
        "decision": "pass", "video": "a.mp4",
        "metadata": {"duration_seconds": 4, "width": 640, "height": 360},
        "checks": [], "frame_evidence": [], "transcript": None,
    })
    args = Namespace(video="a.mp4", spec=None, ocr=False, ocr_lang="eng", asr_model=None,
                     frames=8, output=None, json=True)
    assert cli.cmd_check_video(args) == 3


def test_ffprobe_accounts_for_rotation_and_sar(tmp_path, monkeypatch):
    import vpp.media_qa as qa
    p = tmp_path / "video.mp4"
    p.write_bytes(b"placeholder; ffprobe command is intercepted")
    monkeypatch.setattr(qa, "_need", lambda _: None)
    def fake_command(args, **kwargs):
        return json.dumps({
            "format": {"duration": "10"},
            "streams": [{
                "codec_type": "video", "width": 1920, "height": 1080,
                "sample_aspect_ratio": "1:1",
                "side_data_list": [{"rotation": 90}]
            }]
        })
    monkeypatch.setattr(qa, "_command", fake_command)
    result = qa.probe_video(p)
    assert result["aspect_ratio"] == pytest.approx(9/16, abs=0.0001)
    assert result["rotation_degrees"] == 90


def test_anamorphic_pixel_ratio(tmp_path, monkeypatch):
    import vpp.media_qa as qa
    p = tmp_path / "video.mp4"
    p.write_bytes(b"x")
    monkeypatch.setattr(qa, "_need", lambda _: None)
    monkeypatch.setattr(qa, "_command", lambda args: json.dumps({
        "format": {"duration": "10"},
        "streams": [{"codec_type": "video", "width": 720, "height": 576, "sample_aspect_ratio": "16:15"}]
    }))
    result = qa.probe_video(p)
    assert result["aspect_ratio"] == pytest.approx(4/3, abs=0.0001)
