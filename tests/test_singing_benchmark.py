import pytest

from vpp.singing_benchmark import PAIRED_METHODS, onset_benchmark, paired_summary


def test_missing_word_penalized_and_onset_not_chosen_by_time():
    ref = [{"word": "ein", "start": 1}, {"word": "Verb", "start": 2},
           {"word": "ein", "start": 3}]
    pred = [{"word": "ein", "start": 1.05}, {"word": "ein", "start": 3.15}]
    report = onset_benchmark(ref, pred, 4)
    assert report["wer"] == pytest.approx(1/3)
    assert report["matched_words"] == 2
    assert report["all_word_coverage_100ms"] == pytest.approx(1/3)
    assert report["all_word_coverage_200ms"] == pytest.approx(2/3)
    assert not report["publication_approved"]


def test_invalid_prediction_counts_against_coverage():
    report = onset_benchmark([{"word": "ein", "start": 1}],
                             [{"word": "ein", "start": None}], 2)
    assert report["wer"] == 0
    assert report["all_word_coverage_200ms"] == 0
    assert report["matched_onset_mae_ms"] is None


def test_empty_prediction():
    report = onset_benchmark([{"word": "ein", "start": 1}], [], 2)
    assert report["wer"] == 1 and report["matched_words"] == 0


def test_invalid_reference_refuses_fabricated_onsets():
    with pytest.raises(ValueError):
        onset_benchmark([{"word": "ein Verb", "start": 1}], [], 2)



def test_paired_summary_refuses_incomplete_comparison():
    score = onset_benchmark([{"word": "ein", "start": 1}], [{"word": "ein", "start": 1}], 2)
    rows = [{"track": "a", **dict.fromkeys(PAIRED_METHODS, score)},
            {"track": "b", "raw_whisper": score}]
    report = paired_summary(rows, ["a", "b"])
    assert report["status"] == "incomplete"
    assert report["missing_tracks"] == ["b"]
    assert report["comparison"] is None
    assert not report["publication_approved"]


def test_paired_summary_complete_and_reference_consistency():
    score = onset_benchmark([{"word": "ein", "start": 1}], [{"word": "ein", "start": 1}], 2)
    rows = [{"track": "a", **dict.fromkeys(PAIRED_METHODS, score)}]
    report = paired_summary(rows, ["a"])
    assert report["status"] == "complete"
    assert report["comparison"]["raw_whisper"]["coverage_100ms"] == 1
    assert not report["publication_approved"]
    rows[0]["demucs_whisperx"] = {**score, "reference_words": 2}
    with pytest.raises(ValueError, match="same nonempty reference"):
        paired_summary(rows, ["a"])
