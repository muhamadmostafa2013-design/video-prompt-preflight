"""Independent benchmark and review memory regressions."""
import pytest

from vpp.quality_evidence import benchmark_words, failure_memory, scene_review


def test_known_answer_independent_benchmark():
    ref = [{"word": "Ein", "start": 1, "end": 1.2},
           {"word": "Nomen", "start": 1.2, "end": 1.6}]
    pred = [{"word": "Ein", "start": 1.2, "end": 1.4},
            {"word": "Nomen", "start": 1.4, "end": 1.8}]
    report = benchmark_words(ref, pred)
    assert report["wer"] == 0
    assert report["timing"]["mae_ms"] == 200
    assert report["timing"]["late_starts"] == 2
    assert not report["publication_approved"]
    pred[1]["word"] = "Verb"
    mismatch = benchmark_words(ref, pred)
    assert mismatch["wer"] == .5
    assert mismatch["timing"] is None


def test_scene_missing_and_forbidden_tags():
    expected = [{"id": "a", "start": 0, "end": 3, "required_tags": ["male_character"],
                 "forbidden_tags": ["extra_text"]},
                {"id": "b", "start": 3, "end": 5, "required_tags": ["same_clothing"]}]
    actual = [{"id": "a", "start": 0, "end": 3, "tags": ["extra_text"]}]
    result = scene_review(expected, actual, 5)
    assert {i["code"] for i in result["issues"]} == {
        "required_tag_missing", "forbidden_tag_observed", "missing_observation"}
    assert not result["publication_approved"]


def test_failure_memory_prioritizes_only_known_categories(tmp_path):
    file = tmp_path / "memory.json"
    failure_memory(file, "wrong_caption")
    failure_memory(file, "subtitle_drift")
    result = failure_memory(file, "subtitle_drift")
    assert result["priorities"][0]["category"] == "subtitle_drift"
    assert result["priorities"][0]["count"] == 2
    assert not result["auto_changes_rules"]
    with pytest.raises(ValueError):
        failure_memory(file, "private raw prompt")


def test_empty_prediction_counts_all_words_as_deleted():
    ref = [{"word": "Ein", "start": 1, "end": 1.2}]
    result = benchmark_words(ref, [])
    assert result["wer"] == 1
    assert result["timing"] is None
    assert result["decision"] == "text_mismatch"
