import json

import pytest

from vpp.consensus import (
    audiovisual_review,
    compare_tracks,
    empirical_risk,
    phoneme_review,
)
from vpp.intelligence_planning import (
    cost_plan,
    education_review,
    model_route,
    mutate_prompts,
)
from vpp.intelligence_workflow import guarded_repair, write_dashboard
from vpp.song_alignment import _hash
from vpp.subtitle_sync import parse_srt

HASH = "a"*64


def track(backend, family, delta=0):
    return {"backend": backend, "family": family, "model": backend, "audio_sha256": HASH,
            "words": [{"word": "Ein", "start": 1+delta, "end": 1.3+delta, "score": .9},
                      {"word": "Nomen", "start": 1.4+delta, "end": 1.8+delta, "score": .9}]}


def test_consensus_no_false_independence_or_approval():
    first = track("whisperx", "whisper")
    other = track("faster-whisper", "whisper")
    assert "shared_model_family" in compare_tracks([first, other], HASH)["issues"]
    third = track("ctc", "wav2vec", .05)
    result = compare_tracks([first, third], HASH)
    assert result["decision"] == "review_agreement"
    assert not result["publication_approved"]
    assert not result["human_listening_verified"]
    assert "boundary_disagreement" in compare_tracks([first, track("ctc", "wav2vec", .2)], HASH)["issues"]
    assert "source_hash_mismatch" in compare_tracks([first, {**third, "audio_sha256": "b"*64}], HASH)["issues"]
    assert "duplicate_model_track" in compare_tracks([first, {**first, "family": "other"}], HASH)["issues"]


def test_all_pairs_not_just_primary():
    r = compare_tracks([track("a", "x"), track("b", "y", .09), track("c", "z", -.09)], HASH)
    assert r["decision"] == "blocked"
    assert r["disagreements"][0]["start_spread_ms"] == 180


def test_consensus_missing_or_changed_words():
    a, b = track("a", "x"), track("b", "y")
    b["words"][1]["word"] = "Verb"
    assert "word_sequence_disagrees" in compare_tracks([a, b], HASH)["issues"]
    b["words"] = []
    assert "empty_track" in compare_tracks([a, b], HASH)["issues"]


def test_annotated_phone_and_scene_reviews():
    assert phoneme_review(["a", "ɪ", "n"], ["a", "n"])["phone_error_rate"] == pytest.approx(1/3)
    cues = parse_srt("1\n00:00:01,000 --> 00:00:01,800\nEin Nomen\nاسم\n")
    scenes = [{"id": "a", "start": 0, "end": 1, "required_phrases": ["Ein Nomen"]},
              {"id": "b", "start": 1, "end": 2}]
    assert audiovisual_review(cues, scenes, 2)["issues"][0]["code"] == "required_phrase_outside_scene"


def test_empirical_risk_needs_sample_and_no_duplicate():
    r = [{"id": str(i), "category": "veo", "failed": i < 10} for i in range(50)]
    assert empirical_risk(r[:5], "veo")["decision"] == "insufficient_data"
    result = empirical_risk(r, "veo")
    assert result["observed_failure_rate"] == .2
    assert result["wilson_95"][0] < .2 < result["wilson_95"][1]
    with pytest.raises(ValueError):
        empirical_risk(r+[r[0]], "veo")


def test_cost_planning_never_spends():
    rows = [{"id": "a", "status": "ok", "regenerate_cents": 100},
            {"id": "b", "status": "visual_failed", "regenerate_cents": 100},
            {"id": "c", "status": "subtitle_only", "regenerate_cents": 100}]
    assert cost_plan(rows, 99)["decision"] == "blocked_budget"
    result = cost_plan(rows, 100)
    assert result["estimated_provider_cents"] == 100
    assert result["potential_avoided_cents"] == 200
    assert result["paid_calls"] == 0


def test_router_blocks_unvalidated_and_remote_models():
    a = {"id": "a", "task": "asr", "local": True, "weights_verified": True,
         "benchmark_comparable": True, "required_memory_mb": 1000, "benchmark_loss": .05}
    b = {**a, "id": "b", "local": False, "benchmark_loss": .01}
    assert model_route([a, b], "asr", 2000)["chosen"] == "a"
    assert model_route([a, b], "asr", 10)["chosen"] is None


def test_education_teacher_vocabulary():
    r = education_review({"lyrics": "Ein Nomen ein Verb", "target_vocabulary": ["Ein Nomen"],
                          "cefr": "A1", "curriculum": {"objective": "Nouns",
                          "approved_vocabulary": ["ein", "Nomen"]}})
    assert r["out_of_vocabulary_review"] == ["verb"]
    assert not r["publication_approved"]


@pytest.mark.parametrize("seed", [1, 29, 20261124])
def test_prompt_mutations(seed):
    result = mutate_prompts(seed, 600)
    assert result["failed_trials"] == 0, result["failures"][:3]


def test_dashboard_escapes_and_never_overwrites(tmp_path):
    path = tmp_path / "report.html"
    write_dashboard({"decision": "<script>alert(1)</script>"}, path)
    assert "<script>" not in path.read_text()
    assert "&lt;script&gt;" in path.read_text()
    with pytest.raises(FileExistsError):
        write_dashboard({}, path)


def test_guarded_repair_blocks_same_family_and_preserves_original(tmp_path):
    audio = tmp_path / "source.mp3"
    audio.write_bytes(b"synthetic identity")
    lyrics = tmp_path / "de.txt"
    lyrics.write_text("Ein Nomen")
    srt = tmp_path / "original.srt"
    old = "1\n00:00:02,000 --> 00:00:02,800\nEin Nomen\nاسم\n"
    srt.write_text(old, encoding="utf-8")
    run = tmp_path / "align"
    (run / "asr").mkdir(parents=True)
    raw = run / "asr" / "vocals.json"
    raw.write_text(json.dumps({"word_segments": track("a", "x")["words"]}))
    digest = _hash(audio)
    (run / "alignment_report.json").write_text(json.dumps({
        "decision": "review", "evidence_schema": "vpp.whisperx.words.v1",
        "audio_sha256": digest, "reference_sha256": _hash(lyrics),
        "word_evidence_sha256": _hash(raw), "duration_seconds": 4, "min_score": .5}))
    other = {**track("faster-whisper", "whisper"), "audio_sha256": digest}
    blocked = guarded_repair(audio, lyrics, srt, run, [other], tmp_path / "blocked")
    assert blocked["decision"] == "blocked"
    assert not (tmp_path / "blocked" / "REVIEW_ONLY.srt").exists()
    other = {**track("ctc", "wav2vec"), "audio_sha256": digest}
    result = guarded_repair(audio, lyrics, srt, run, [other], tmp_path / "review")
    assert result["decision"] == "review"
    assert result["after"]["metrics"]["max_absolute_ms"] == 0
    assert srt.read_text(encoding="utf-8") == old
    assert not result["publication_approved"]


def test_appearance_continuity_flags_nonmatching_samples():
    from vpp.model_evidence import continuity_signals
    samples = [
        {"appearance_group": "costume", "seconds": 1, "appearance": {
            "expected": "a blue jacket", "signal": "supports_expected"}},
        {"appearance_group": "costume", "seconds": 3, "appearance": {
            "expected": "a blue jacket", "signal": "alternative_ranked_higher"}},
    ]
    result = continuity_signals(samples)
    assert result["groups"][0]["status"] == "appearance_review"
    assert result["groups"][0]["flagged_seconds"] == [3]
    assert not result["publication_approved"]


def test_consensus_invalid_ctc_timing_blocks_with_diagnostics():
    a = track("whisperx", "whisper")
    b = track("wav2vec2-ctc", "wav2vec2")
    b["words"][0]["end"] = b["words"][0]["start"]
    report = compare_tracks([a, b], HASH)
    assert report["decision"] == "blocked"
    assert "invalid_word_timestamps" in report["issues"]
    assert report["invalid_tracks"][0]["backend"] == "wav2vec2-ctc"
    assert not report["publication_approved"]
    b = track("faster-whisper", "unrelated")
    assert "model_family_mismatch" in compare_tracks([a, b], HASH)["issues"]


def test_dashboard_displays_per_model_drift_without_fabricating_missing_values(tmp_path):
    path = tmp_path / "report.html"
    evidence = {"backend": "<script>model</script>", "model": "fixture",
                "cue_drift_summary": {"measured_cues": 1, "unmeasured_cues": 1,
                                      "drift_candidates": 1, "boundary_max_ms": 300},
                "cue_drift": [
                    {"cue": 1, "text": "Ein <img src=x onerror=alert(1)> Haus",
                     "onset_error_ms": 300, "offset_error_ms": -200, "status": "drift_candidate"},
                    {"cue": 2, "text": "ein Verb", "status": "incomplete_acoustic_evidence"}]}
    write_dashboard({"stages": {"acoustic_drift_1": {"status": "completed", "evidence": evidence}}}, path)
    doc = path.read_text(encoding="utf-8")
    assert "Acoustic caption review" in doc
    assert "<th scope=\"col\">Onset error</th>" in doc
    assert "<td>300</td><td>-200</td>" in doc
    assert "<td>—</td>" in doc
    assert "<script>" not in doc and "<img" not in doc
    assert "&lt;script&gt;model&lt;/script&gt;" in doc
    assert "incomplete_acoustic_evidence" in doc


@pytest.mark.parametrize("same_family,expected_exit", [(True, 2), (False, 3)])
def test_consensus_cli_exit_distinguishes_blocked_from_review(tmp_path, capsys, same_family, expected_exit):
    from argparse import Namespace

    from vpp.intelligence_workflow import _consensus

    audio = tmp_path / "source.wav"
    audio.write_bytes(b"fixture")
    first = track("whisperx", "whisper")
    second = track("faster-whisper", "whisper") if same_family else track("ctc", "wav2vec")
    paths = []
    for i, data in enumerate([first, second]):
        data["audio_sha256"] = _hash(audio)
        path = tmp_path / f"track-{i}.json"
        path.write_text(json.dumps(data))
        paths.append(str(path))
    assert _consensus(Namespace(audio=str(audio), tracks=paths, tolerance_ms=100)) == expected_exit
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == ("blocked" if same_family else "review_agreement")
    assert not result["publication_approved"]
