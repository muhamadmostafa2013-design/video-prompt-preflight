"""Regression tests for deterministic German Educational Music QA."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from vpp.german_music_qa import compile_song_prompt, review_song

ROOT = Path(__file__).resolve().parents[1]


def example():
    return yaml.safe_load((ROOT / "examples/german_animals_song.yml").read_text(encoding="utf-8"))


def test_valid_animals_song_clears_preflight():
    report = review_song(example())
    assert report["passed"]
    assert report["decision"] == "preflight_pass"
    assert report["target_counts"] == {"der Hund": 2, "die Katze": 2, "das Pferd": 2}
    assert report["risk_score"] == 0
    assert report["manual_checks"]


def test_article_agreement_error_blocks():
    spec = example()
    spec["lyrics"] = spec["lyrics"].replace("der Hund", "die Hund")
    report = review_song(spec)
    assert not report["passed"]
    ids = {x["rule_id"] for x in report["findings"]}
    assert "music.article.mismatch" in ids
    assert "music.target.missing" in ids


def test_missing_target_blocks():
    spec = example()
    spec["target_vocabulary"].append("der Frosch")
    result = review_song(spec)
    assert result["decision"] == "block"
    assert result["target_counts"]["der Frosch"] == 0


def test_low_repetitions_needs_review():
    spec = example()
    spec["min_repetitions"] = 3
    result = review_song(spec)
    assert result["passed"]
    assert result["decision"] == "review"
    assert {x["rule_id"] for x in result["findings"]} == {"music.target.repetition"}


def test_german_only_policy_does_not_silently_accept_arabic():
    spec = example()
    spec["lyrics"] += "\nمرحباً"
    assert "music.lyrics.arabic" in {x["rule_id"] for x in review_song(spec)["findings"]}
    spec["allow_bilingual"] = True
    assert "music.lyrics.arabic" not in {x["rule_id"] for x in review_song(spec)["findings"]}


def test_no_vocals_conflict_blocks():
    spec = example()
    spec["instrumental_only"] = True
    assert "music.vocals.conflict" in {x["rule_id"] for x in review_song(spec)["findings"]}


def test_unknown_noun_is_not_falsely_certified():
    spec = example()
    spec["lyrics"] += "\nder Löffel singt"
    assert "music.article.mismatch" not in {x["rule_id"] for x in review_song(spec)["findings"]}
    assert "grammar" in review_song(spec)["limitations"].lower()


def test_exact_lyrics_preserved_by_compiler():
    spec = example()
    compiled = compile_song_prompt(spec)
    assert "EXACT LYRICS START\n" + spec["lyrics"].strip() + "\nEXACT LYRICS END" in compiled
    assert "Do not invent extra lyrics" in compiled


def test_blocked_song_cannot_be_compiled():
    spec = example()
    spec["lyrics"] = ""
    with pytest.raises(ValueError, match="blocked"):
        compile_song_prompt(spec)


@pytest.mark.parametrize("bad", [
    "not a spec",
    {"lyrics": []},
    {"lyrics": "Hallo", "target_vocabulary": "der Hund"},
    {"lyrics": "Hallo", "age_range": [9, 4]},
    {"lyrics": "Hallo", "bpm": 0},
    {"lyrics": "Hallo", "bpm": float("nan")},
    {"lyrics": "Hallo", "target_vocabulary": [42]},
])
def test_invalid_inputs_fail_cleanly(bad):
    with pytest.raises((TypeError, ValueError)):
        review_song(bad)


def test_missing_tempo_and_targets_are_advisory():
    spec = {"lyrics": "Guten Morgen!", "vocal_direction": "Clear Standard German"}
    report = review_song(spec)
    assert report["decision"] == "review"
    assert {"music.bpm.missing", "music.targets.missing"} <= {f["rule_id"] for f in report["findings"]}


def test_lyrics_target_matching_uses_word_boundaries():
    spec = example()
    spec["lyrics"] = "Die Hundertwasser-Schule!" * 2
    assert review_song(spec)["target_counts"]["der Hund"] == 0


def test_cli_music_qa_json_and_prompt_out(tmp_path):
    destination = tmp_path / "prompt.txt"
    completed = subprocess.run(
        [sys.executable, "-m", "vpp.cli", "music-qa",
         str(ROOT / "examples/german_animals_song.yml"),
         "--json", "--prompt-out", str(destination)],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["decision"] == "preflight_pass"
    assert destination.exists()
    assert "der Hund" in destination.read_text(encoding="utf-8")
