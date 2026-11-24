import pytest

from vpp.acoustic_models import collapse_phones, ctc_timing_issues, native_boundary


def test_ctc_collapses_only_consecutive_ids_before_removing_blank():
    vocab = {"<pad>": 0, "a": 1, "n": 2, "<unk>": 3}
    assert collapse_phones([1, 1, 0, 1, 2, 2, 3], vocab, 0) == ["a", "a", "n", "[uncertain:<unk>]"]
    with pytest.raises(ValueError):
        collapse_phones([9], vocab, 0)


def test_ctc_invalid_boundaries_are_not_mutated():
    words = [{"word": "Ein", "start": 1.0, "end": 1.2},
             {"word": "Nomen", "start": 1.1, "end": 1.1},
             {"word": "Verb", "start": 1.1, "end": 1.5}]
    assert {i["code"] for i in ctc_timing_issues(words, 2)} == {
        "invalid_or_out_of_range_interval", "overlapping_boundary"}
    assert words[1]["start"] == words[1]["end"] == 1.1


def test_model_numeric_scalar_conversion_preserves_value():
    class ModelScalar(float):
        pass
    value = ModelScalar(3.582)
    boundary = native_boundary(value)
    assert type(boundary) is float
    assert boundary == value
    assert native_boundary(None) is None
    assert native_boundary(True) is None
    assert native_boundary(float("inf")) is None
    assert native_boundary("3.582") is None
