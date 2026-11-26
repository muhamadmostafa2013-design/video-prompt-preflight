import pytest

from vpp.acoustic_review import preserve_unaligned_words, review_evidence, unique_matches
from vpp.song_alignment import _hash


def test_repeated_words_cannot_be_arbitrarily_matched():
    cost, rows = unique_matches(["ein", "Haus".lower(), "ein", "haus"], ["ein", "haus"])
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
    with pytest.raises(ValueError, match="SHA-256"):
        review_evidence(audio, srt, {**evidence, "audio_sha256": "0"*64})
