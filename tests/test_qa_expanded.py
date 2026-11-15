"""Intensive cross-layer regression suite. Deterministic, offline and CI reproducible."""
from __future__ import annotations

import copy
import json
import math
import random
import re
import subprocess
from pathlib import Path

import pytest

from vpp import jev_judge
from vpp.analyzer import analyze_scene
from vpp.candidates import build_candidates
from vpp.compiler import compile_scene
from vpp.jev_judge import candidate_utility, derive_gate
from vpp.knowledge import evaluate_knowledge, load_pack
from vpp.media_qa import MediaQAError, detect_silent_audio, inspect_video, probe_video, sample_frames
from vpp.optimizer import optimize_prompt
from vpp.parser import parse_prompt
from vpp.prompt_analyzer import analyze_prompt
from vpp.triple_review import triple_review

ROOT = Path(__file__).resolve().parents[1]
PACKS = sorted(p.stem for p in (ROOT / "src/vpp/knowledge_packs").glob("*.yml"))


def timed_scene():
    return parse_prompt(
        "Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nsich verlaufen\n"
        "TIMELINE:\n3-5s show laufen\n7-9s show sich verlaufen"
    )


def test_all_candidates_preserve_explicit_absolute_timing():
    scene = timed_scene()
    candidates = build_candidates(scene, "veo")
    assert len(candidates) == 3
    for c in candidates:
        assert re.search(r"3(?:\.0)?-5(?:\.0)?s", c.prompt), c.name
        assert re.search(r"7(?:\.0)?-9(?:\.0)?s", c.prompt), c.name
        assert "0-2s" not in c.prompt
        assert c.hard_constraint_coverage == 100
    selected = triple_review(
        "Create a 10 second 9:16 video.\nTIMELINE:\n3-5s show intro\n7-9s show ending",
        provider="veo"
    )
    assert selected["passed"]
    assert "3-5s" in selected["final_prompt"]
    assert "7-9s" in selected["final_prompt"]


def test_exact_word_morphs_require_hard_cuts_but_camera_motion_is_intact():
    text = "Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nsich verlaufen\nTIMELINE:\n0-10s transform laufen into sich verlaufen"
    for c in build_candidates(parse_prompt(text), "veo"):
        assert "hard cut" in c.prompt.lower()
    camera = "Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nTIMELINE:\n0-10s animate the camera to the presenter"
    for c in build_candidates(parse_prompt(camera), "veo"):
        assert "animate the camera to the presenter" in c.prompt
        assert "show the camera as static text" not in c.prompt


@pytest.mark.parametrize("duration", [math.nan, math.inf, -math.inf, -1, 0, True, "10", None, 10**4000])
def test_bad_duration_blocks_without_crashing(duration):
    report = analyze_scene({"duration_seconds": duration, "rules": {}})
    assert not report.passed
    assert "duration.missing" in {f.rule_id for f in report.findings}


@pytest.mark.parametrize("timeline", ["text", 3, {"start": 1}, [None], [5], ["bad"]])
def test_bad_timeline_blocks_without_crashing(timeline):
    report = analyze_scene({"duration_seconds": 10, "timeline": timeline})
    assert not report.passed
    assert {"timeline.type", "timeline.invalid"} & {f.rule_id for f in report.findings}


@pytest.mark.parametrize("rules", ["text", [], 3, True])
def test_nonmapping_rules_block_without_crashing(rules):
    report = analyze_scene({"duration_seconds": 10, "rules": rules})
    assert not report.passed
    assert "rules.type" in {f.rule_id for f in report.findings}


def test_unhashable_whitelist_blocks_without_crashing():
    report = analyze_scene({"duration_seconds": 10, "screen_text": ["hi"], "text_whitelist": [{"bad": 1}]})
    assert not report.passed
    assert "screen_text.whitelist_type" in {f.rule_id for f in report.findings}


def test_invalid_rule_settings_do_not_mutate_caller():
    scene = {"duration_seconds": 10, "rules": {"max_screen_text_items": "bad"}}
    original = copy.deepcopy(scene)
    report = analyze_scene(scene)
    assert not report.passed
    assert "rules.invalid" in {f.rule_id for f in report.findings}
    assert scene == original


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_jev_scores_always_block(bad):
    kwargs = dict(
        hard_constraints_probability=.99, provider_fit_probability=.99,
        human_review_probability=.01, risk_score=.1, dominant_risk="none",
        score_confidence=.99, choice_confidence=.99
    )
    for key in ("hard_constraints_probability", "provider_fit_probability",
                "human_review_probability", "risk_score",
                "score_confidence", "choice_confidence"):
        result = derive_gate(**{**kwargs, key: bad})
        assert result.decision == "block", (key, bad, result)
        assert result.dominant_risk == "invalid_probability_data"
    utility = candidate_utility(
        hard_constraints_probability=bad, provider_fit_probability=.9,
        ambiguity_probability=.1, risk_score=.5,
        deterministic_score=95, hard_constraint_coverage=100
    )
    assert utility < 0 and math.isfinite(utility)


def test_jev_selected_candidate_missing_hard_constraints_cannot_release(monkeypatch):
    review = {"passed": True, "final_prompt": "source",
              "rounds": [{"candidates": [{"name": "A", "prompt": "source"}]}]}
    monkeypatch.setattr(jev_judge, "_client_and_types",
                        lambda client: (client, False, None, None, None))
    monkeypatch.setattr(jev_judge, "jev_rank_candidates", lambda *args, **kw: {
        "winner": {"hard_constraint_coverage": 60, "utility": .99},
        "winner_prompt": "unsafe", "ranking": [],
    })
    monkeypatch.setattr(jev_judge, "jev_gate",
                        lambda *args, **kw: pytest.fail("Blocking candidate must not reach remote semantic gate"))
    result = jev_judge.jev_review(review, original_prompt="source", client=object())
    assert result["decision"] == "block"


def test_nonfinite_ranked_candidate_is_not_valid_json_nan():
    rows = [{"key": "c0", "name": "bad", "hard_constraints_probability": math.nan,
             "provider_fit_probability": .99, "ambiguity_probability": .01,
             "risk_score": .01, "deterministic_score": 100, "hard_constraint_coverage": 100}]
    ranked = jev_judge.rank_candidate_scores(rows)
    assert ranked[0].utility < 0
    json.dumps([c.to_dict() for c in ranked], allow_nan=False)


@pytest.mark.parametrize("pack", PACKS)
def test_each_provider_pack_parses_and_evaluates_offline(pack):
    loaded = load_pack(pack)
    assert isinstance(loaded, dict) and isinstance(loaded.get("rules"), list)
    seen = set()
    for rule in loaded["rules"]:
        assert rule["id"] not in seen
        seen.add(rule["id"])
        assert rule.get("severity") in {"error", "warning", "info"}
        assert isinstance(rule.get("sources", []), list)
    scene = parse_prompt("Create a 10 second 9:16 video.\nON SCREEN:\nlaufen")
    results = evaluate_knowledge("Create a 10 second 9:16 video.", scene, pack)
    assert len(results) == len({(r.rule_id, r.provider_scope) for r in results})


def test_provider_pack_cannot_escape_package_directory():
    with pytest.raises(ValueError):
        load_pack("../../../examples/ver_scene_1")


def test_fuzz_500_multilingual_mixed_prompts_stable():
    rng = random.Random(32456)
    pieces = ["Create a 10 second 9:16 video.", "ON SCREEN:", "laufen",
              "sich verlaufen", "TIMELINE:", "0-5s show intro",
              "5-10s show outro", "بدون موسيقى", "No subtitles.",
              "Do not add music.", "<img src=x>", "كاميرا", "🌍", "\u202e"]
    for _ in range(500):
        text = " ".join(rng.choice(pieces) for _ in range(rng.randint(1, 14)))
        scene, report = analyze_prompt(text)
        assert analyze_prompt(text)[1].to_dict() == report.to_dict()
        assert isinstance(compile_scene(scene), str)
        assert isinstance(optimize_prompt(text)["requires_review"], bool)


def test_real_media_with_audio_and_ocr_remains_advisory(tmp_path):
    if not all(__import__("shutil").which(x) for x in ("ffmpeg", "ffprobe")):
        pytest.skip("FFmpeg not available in this matrix")
    video = tmp_path / "sample video.mp4"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", "color=c=blue:s=320x180:r=12:d=2", "-t", "2",
        "-c:v", "mpeg4", str(video)
    ], check=True, capture_output=True, timeout=30)
    meta = probe_video(video)
    assert meta["duration_seconds"] == pytest.approx(2, abs=.2)
    assert meta["has_audio"] is False
    report = inspect_video(video, {"spoken": {"arabic": "مرحبا"}})
    assert report["decision"] == "fail"
    assert "expected_speech_audio" in {c["name"] for c in report["checks"]}
    samples = sample_frames(video, 2, 3, tmp_path)
    assert len(samples) == 3 and all(s["path"].exists() for s in samples)


def test_no_remote_protocol_media_probe(tmp_path):
    if not __import__("shutil").which("ffprobe"):
        pytest.skip("ffprobe unavailable")
    playlist = tmp_path / "remote.m3u8"
    playlist.write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:2,\nhttp://127.0.0.1:65535/private.ts\n#EXT-X-ENDLIST\n",
        encoding="utf-8"
    )
    with pytest.raises(MediaQAError):
        probe_video(playlist)
