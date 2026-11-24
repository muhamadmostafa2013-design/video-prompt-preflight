import pytest

from vpp.singing_benchmark import onset_benchmark


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
