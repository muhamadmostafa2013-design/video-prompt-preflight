import pytest

from vpp.acoustic_review import (
    preserve_unaligned_words,
    review_evidence,
    unique_matches,
)
from vpp.song_alignment import _hash


def test_repeated_words_cannot_be_arbitrarily_matched():
    cost, rows = unique_matches(["ein", "haus", "ein", "haus"], ["ein", "haus"])
    assert cost == 2
    assert all(row["unique"] is None for row in rows)


def test_exact_repetition_with_full_coverage_is_unique():
    _, rows = unique_matches(["ein", "ein"], ["ein", "ein"])
    assert [row["unique"] for row in rows] == [0, 1]


def test_substitution_does_not_inherit_timestamp():
    _, rows = unique_matches(["termin", "vereinbaren"], ["antrag", "vereinbaren"])
    assert [row["unique"] for row in rows] == [None, 1]


def test_failed_alignment_retains_recognized_text_without_times():
    assert preserve_unaligned_words("Ein Haus", [{"word": "Haus", "start": 2}]) == [
        {"word": "ein", "start": None, "end": None},
        {"word": "haus", "start": None, "end": None}]
    assert preserve_unaligned_words("Haus", [{"word": "Haus"}])[0]["start"] is None


def test_review_source_binding_and_invalid_timestamps(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fixture")
    srt = tmp_path / "source.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nEin Haus\nمنزل\n", encoding="utf-8")
    evidence = {"audio_sha256": _hash(audio), "duration": 5,
                "words": [{"word": "Ein", "start": .1, "end": .3},
                          {"word": "Haus", "start": None, "end": None}]}
    report = review_evidence(audio, srt, evidence)
    assert report["candidate_matches"] == 1
    assert report["rows"][1]["status"] == "invalid_timing"
    assert report["rows"][0]["screen_start"] == 1
    assert report["rows"][0]["start"] == .1
    assert not report["publication_approved"]
    assert review_evidence(audio, srt, {**evidence, "words": []})["decision"] == "blocked_empty_asr"
    assert review_evidence(audio, srt, {**evidence, "words": [{"word": "!"}]})["decision"] == "blocked_empty_asr"
    with pytest.raises(ValueError, match="SHA-256"):
        review_evidence(audio, srt, {**evidence, "audio_sha256": "0"*64})


def _drift_fixture(tmp_path, text, words, start="00:00:01,000", end="00:00:02,000"):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fixture")
    srt = tmp_path / "source.srt"
    srt.write_text(f"1\n{start} --> {end}\n{text}\n", encoding="utf-8")
    return review_evidence(audio, srt, {"audio_sha256": _hash(audio),
                          "duration": 5, "words": words})


def test_drift_sign_and_summary(tmp_path):
    report = _drift_fixture(tmp_path, "Ein Haus", [
        {"word": "Ein", "start": .7, "end": .9},
        {"word": "Haus", "start": 1.0, "end": 2.2}])
    cue = report["cue_drift"][0]
    assert cue["onset_error_ms"] == 300
    assert cue["offset_error_ms"] == -200
    assert cue["status"] == "drift_candidate"
    assert report["cue_drift_summary"]["boundary_mae_ms"] == 250
    assert report["cue_drift_summary"]["boundary_p95_ms"] == 300
    assert report["decision"] == "review_only"
    assert not report["publication_approved"]


def test_drift_within_threshold(tmp_path):
    report = _drift_fixture(tmp_path, "Haus", [
        {"word": "Haus", "start": .85, "end": 2.15}])
    assert report["cue_drift"][0]["status"] == "within_tolerance"


@pytest.mark.parametrize("text,words,status", [
    ("Ein Haus", [{"word": "Ein", "start": .7, "end": .9}],
     "incomplete_acoustic_evidence"),
    ("Ein Haus", [{"word": "Ein", "start": .7, "end": .9},
                  {"word": "großes", "start": 1, "end": 1.3},
                  {"word": "Haus", "start": 1.4, "end": 2}],
     "noncontiguous_acoustic_evidence"),
    ("Ein Ein", [{"word": "Ein", "start": .7, "end": .9}],
     "incomplete_acoustic_evidence"),
    ("Haus", [{"word": "Haus", "start": None, "end": None}],
     "incomplete_acoustic_evidence"),
])
def test_drift_withholds_unreliable_boundaries(tmp_path, text, words, status):
    report = _drift_fixture(tmp_path, text, words)
    assert report["cue_drift"][0]["status"] == status
    assert "onset_error_ms" not in report["cue_drift"][0]
    assert report["cue_drift_summary"]["boundary_mae_ms"] is None
    assert report["cue_drift_summary"]["unmeasured_cues"] == 1


def test_out_of_range_cue(tmp_path):
    report = _drift_fixture(tmp_path, "Haus", [
        {"word": "Haus", "start": 1, "end": 2}], end="00:00:06,000")
    assert report["cue_drift"][0]["status"] == "screen_out_of_range"


def test_punctuation_only_reference_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="lexical reference"):
        _drift_fixture(tmp_path, "!!!", [])
