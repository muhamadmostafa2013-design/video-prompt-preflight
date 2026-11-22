"""AI Prompt Director: real educational examples, negative gates and CLI regressions."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vpp import production
from vpp.director import review_job

ROOT = Path(__file__).resolve().parents[1]


def campus():
    return production.validate_job(
        production._yaml(ROOT / "examples/production_university_video.yml"), ROOT
    )


def song():
    return production.validate_job(
        production._yaml(ROOT / "examples/production_animals_song.yml"), ROOT
    )


def pretend_reviews(job, passed=True):
    return [{"passed": passed} for _ in job["scenes"]]


def evaluate(job, passed=True):
    return review_job(
        job, [scene["prompt"] for scene in job["scenes"]],
        vpp_results=pretend_reviews(job, passed),
    )


def rules(report):
    return {f["rule_id"] for f in report["findings"]}


def test_real_campus_passes_full_director_and_preserves_dialogue():
    job = campus()
    result = production.evaluate_preflight(job)
    assert result["director"]["decision"] == "ready_for_generation"
    assert result["director"]["ready_for_generation"]
    assert len(result["prompts"]) == 2
    assert "Entschuldigung, wo ist die Mensa?" in result["prompts"][0]
    assert job["continuity_anchor"] in result["prompts"][0]
    assert job["continuity_anchor"] in result["prompts"][1]
    assert result["director"]["manual_post_generation_checks"]


def test_song_full_director_checks_lyrics_and_objective():
    job = song()
    result = production.evaluate_preflight(job)
    assert result["director"]["ready_for_generation"]
    assert result["qa"]["passed"]


def test_missing_objective_blocks():
    job = campus()
    job["learning_objective"] = ""
    report = evaluate(job)
    assert report["decision"] == "blocked"
    assert "director.objective.missing" in rules(report)


def test_invalid_cefr_and_age_block():
    job = campus()
    job["cefr_level"] = "whatever"
    job["learner_age"] = ["young", "old"]
    report = evaluate(job)
    assert {"director.cefr.missing", "director.age.missing"} <= rules(report)


def test_missing_educational_target_blocks():
    job = campus()
    job["target_phrases"] = ["Das Wohnheim ist teuer."]
    assert "director.target.not_spoken" in rules(evaluate(job))


def test_changed_dialogue_is_detected():
    job = campus()
    job["scenes"][0]["expected_dialogue"][0]["text"] = "Wo ist die Bibliothek?"
    assert "director.dialogue.not_in_prompt" in rules(evaluate(job))


def test_unknown_speaker_is_detected():
    job = campus()
    job["scenes"][0]["expected_dialogue"][0]["speaker"] = "Unexpected Third Student"
    assert "director.speaker.not_in_cast" in rules(evaluate(job))


def test_article_mismatch_is_detected_from_approved_dialogue():
    job = campus()
    job["scenes"][0]["expected_dialogue"][0]["text"] = "Das ist die Hund."
    job["scenes"][0]["prompt"] += ' Student A says "Das ist die Hund."'
    assert "director.article.check" in rules(evaluate(job))


def test_missing_multi_scene_continuity_blocks():
    job = campus()
    job["continuity_anchor"] = ""
    assert "director.continuity.missing" in rules(evaluate(job))
    job["continuity_anchor"] = "Two identical students in blue jackets."
    job["cast"] = []
    assert "director.cast.missing" in rules(evaluate(job))


def test_video_caption_conflict_blocks_before_api():
    job = campus()
    job["scenes"][1]["prompt"] += " Add automatic subtitles."
    assert "director.captions.conflict" in rules(evaluate(job))


def test_speech_overflow_or_tight_needs_revision():
    job = campus()
    repeated = "Entschuldigung, wo ist die Mensa? " * 9
    job["scenes"][0]["expected_dialogue"][0]["text"] = repeated.strip()
    job["scenes"][0]["prompt"] += " " + repeated
    assert "director.speech.overflow" in rules(evaluate(job))


def test_vpp_failure_blocks_director():
    assert "director.vpp.blocked" in rules(evaluate(campus(), passed=False))


def test_missing_vpp_review_blocks():
    job = campus()
    report = review_job(job, [scene["prompt"] for scene in job["scenes"]], [])
    assert "director.vpp.missing" in rules(report)


def test_recast_warning_requires_revision():
    job = campus()
    job["scenes"][0]["prompt"] += " New actors are replacing the students."
    report = evaluate(job)
    assert report["decision"] == "needs_revision"
    assert not report["ready_for_generation"]


def test_song_cefr_mismatch_blocks():
    job = song()
    job["cefr_level"] = "C2"
    result = review_job(job, ["song prompt"], music_report={"passed": True, "decision": "preflight_pass"})
    assert "director.cefr.mismatch" in rules(result)


def test_music_warning_needs_revision():
    job = song()
    result = review_job(job, ["song prompt"], music_report={"passed": True, "decision": "review"})
    assert result["decision"] == "needs_revision"


def test_paid_mode_never_calls_api_when_director_blocks(tmp_path, monkeypatch):
    wrong = campus()
    wrong["learning_objective"] = ""
    source = tmp_path / "bad.yml"
    import yaml

    source.write_text(
        yaml.safe_dump({
            "type": "video", "title": wrong["title"], "aspect_ratio": wrong["aspect_ratio"],
            "learning_objective": wrong["learning_objective"], "cefr_level": wrong["cefr_level"],
            "learner_age": wrong["learner_age"], "target_phrases": wrong["target_phrases"],
            "cast": wrong["cast"], "continuity_anchor": wrong["continuity_anchor"],
            "scenes": [{k: v for k, v in s.items() if k != "id"} for s in wrong["scenes"]],
        }, allow_unicode=True), encoding="utf-8"
    )
    monkeypatch.setattr(
        production, "generate_paid",
        lambda *_args: pytest.fail("Forbidden: Gemini API reached"),
    )
    target = tmp_path / "render"
    with pytest.raises(production.ProductionError, match="AI Prompt Director"):
        production.produce(
            source, tmp_path, target, mode="paid", max_estimated_usd=5.0,
            environ={"GEMINI_API_KEY": "dummy", "VPP_ALLOW_PAID_GENERATION": "YES"},
        )
    assert not target.exists()


def test_cli_produces_json_and_approved_prompt(tmp_path):
    report_path = tmp_path / "report.json"
    prompt_path = tmp_path / "prompt.txt"
    proc = subprocess.run(
        [sys.executable, "-m", "vpp.cli", "director-review",
         "examples/production_university_video.yml", "--json", "-o",
         str(report_path), "--prompt-out", str(prompt_path)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)["director"]
    assert report["decision"] == "ready_for_generation"
    assert report_path.is_file()
    assert prompt_path.is_file()
    assert "Mensa" in prompt_path.read_text(encoding="utf-8")


def test_cli_blocks_bad_job_without_writing_generator_prompt(tmp_path):
    import yaml

    source = tmp_path / "bad.yml"
    spec = copy.deepcopy(production._yaml(ROOT / "examples/production_university_video.yml"))
    spec["target_phrases"] = ["Niemals vorhanden."]
    source.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    target = tmp_path / "do-not-generate.txt"
    proc = subprocess.run(
        [sys.executable, "-m", "vpp.cli", "director-review", str(source),
         "--root", str(ROOT), "--json", "--prompt-out", str(target)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 2, proc.stderr
    assert not target.exists()
    result = json.loads(proc.stdout)["director"]
    assert "director.target.not_spoken" in rules(result)
