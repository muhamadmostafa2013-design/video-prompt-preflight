"""Independent bug regressions discovered after 0.5.2. These gates are behavior tests."""
from __future__ import annotations

from vpp.analyzer import analyze_scene
from vpp.parser import parse_prompt
from vpp.prompt_analyzer import analyze_prompt
from vpp.optimizer import optimize_prompt
from vpp.cli import cmd_check_video
from argparse import Namespace


def ids(text):
    scene, report = analyze_prompt(text)
    return scene, {f.rule_id for f in report.findings}


def test_inline_hold_after_scene_duration_is_not_another_duration():
    scene, findings = ids("Create a 10 second video and hold for 2 seconds; show a flower.")
    assert scene["parse_meta"]["duration_mentions"] == [10]
    assert "prompt.duration.conflict" not in findings


def test_ordinary_show_action_is_not_an_on_screen_text_header():
    scene = parse_prompt("Create a 10 second 9:16 video.\nShow a dramatic sunset.\nWarm studio lighting.\nCamera zooms slowly.")
    assert scene["screen_text"] == []


def test_explicit_screen_text_header_still_extracts_whitelist():
    scene = parse_prompt("Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nsich verlaufen\n")
    assert scene["screen_text"] == ["laufen", "sich verlaufen"]


def test_negated_add_music_does_not_flip_positive_instruction():
    scene, findings = ids("Create a 10 second 9:16 video. Do not add background music.")
    assert scene["rules"]["no_background_music"] is True
    assert "prompt.music.conflict" not in findings


def test_negated_show_subtitles_sets_negative_policy():
    scene, findings = ids("Create a 10 second 9:16 video. Do not show subtitles.")
    assert scene["rules"]["no_auto_subtitles"] is True
    assert "prompt.subtitle.conflict" not in findings


def test_real_subtitle_conflict_detected():
    _, findings = ids("Create a 10 second 9:16 video. No subtitles. Show subtitles.")
    assert "prompt.subtitle.conflict" in findings


def test_arabic_no_music_writes_rule_and_calls_for_review():
    scene, findings = ids("اعمل فيديو مدته عشر ثواني بدون موسيقى")
    assert scene["rules"]["no_background_music"] is True
    assert "prompt.arabic.limited" in findings


def test_overlapping_absolute_timeline_is_blocking():
    scene = parse_prompt("Create a 10 second 9:16 video.\nTIMELINE:\n0-5s show intro\n4-8s show outro")
    report = analyze_scene(scene)
    assert "timeline.overlap" in {f.rule_id for f in report.findings}
    assert not report.passed


def test_invalid_end_before_start_and_negative_events_fail():
    scene = {"duration_seconds":10, "screen_text":[], "rules":{},
             "timeline":[{"start":5,"end":4,"seconds":-1,"action":"invalid"}]}
    report = analyze_scene(scene)
    assert "timeline.invalid" in {f.rule_id for f in report.findings}


def test_optimizer_missing_scene_duration_cannot_release_unverified_default():
    result = optimize_prompt("Show a cinematic flower, no other instructions")
    assert result["requires_review"] is True
    assert any("placeholder" in d for d in result["decisions"])


def test_media_qa_empty_scene_spec_must_not_be_pass(monkeypatch, capsys):
    import vpp.cli as cli
    monkeypatch.setattr(cli, "load_scene", lambda _: {})
    monkeypatch.setattr(cli, "inspect_video", lambda *a, **k: {
        "decision":"pass", "video":"x.mp4",
        "metadata":{"duration_seconds":10,"width":1080,"height":1920},
        "checks":[], "frame_evidence":[], "transcript":None
    })
    ns=Namespace(video="x.mp4",spec="empty.yaml",ocr=False,ocr_lang="eng",
                 asr_model=None,frames=8,output=None,json=True)
    assert cmd_check_video(ns) == 3


def test_explicit_duration_can_follow_inference_context():
    scene = parse_prompt("Hold for 2 seconds, then create a 10-second video")
    assert scene["duration_seconds"] == 10
    assert scene["parse_meta"]["duration_mentions"] == [10]
