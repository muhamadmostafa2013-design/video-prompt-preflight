import json

import pytest

from vpp.cli import main
from vpp.song_alignment import _hash
from vpp.speech_timing_benchmark import REFERENCE_SCHEMA, score


def row(word, start, end):
    return {"word": word, "start": start, "end": end}


@pytest.fixture
def bundle(tmp_path):
    audio = tmp_path / "fixture.wav"
    audio.write_bytes(b"synthetic source bytes for testing source binding only")
    source = {"audio_sha256": _hash(audio), "source_duration_seconds": 4}
    reference = {**source, "schema": REFERENCE_SCHEMA, "words": [row("ich", .2, .4), row("lerne", .7, 1.2)]}
    evidence = {**source, "words": [row("ich", .25, .45), row("lerne", .8, 1.4)]}
    return audio, reference, evidence


def test_full_coverage_uses_both_boundaries(bundle):
    result = score(*bundle)
    assert result["wer"] == 0
    assert result["timed_unique_matches"] == 2
    assert result["both_boundaries_all_word_coverage_100ms"] == .5
    assert result["both_boundaries_all_word_coverage_200ms"] == 1
    assert result["matched_onset_only"] == {"mae_ms": 75, "p95_ms": 100}
    assert result["matched_offset_only"] == {"mae_ms": 125, "p95_ms": 200}
    assert result["publication_approved"] is False


def test_repeats_and_missing_times_never_enter_numerator(bundle):
    audio, reference, evidence = bundle
    reference["words"] = [row("ich", .2, .4), row("ich", .5, .65), row("lerne", .7, 1.2)]
    evidence["words"] = [row("ich", .2, .4), row("lerne", None, None)]
    result = score(audio, reference, evidence)
    assert result["word_errors"] == 1
    assert result["ambiguous_reference_words"] == 2
    assert result["invalid_timing_reference_words"] == 1
    assert result["both_boundaries_all_word_coverage_200ms"] == 0
    assert result["matched_onset_only"]["mae_ms"] is None


def test_empty_asr_is_zero_coverage_not_zero_error(bundle):
    audio, reference, evidence = bundle
    evidence["words"] = []
    result = score(audio, reference, evidence)
    assert result["wer"] == 1
    assert result["unmatched_reference_words"] == 2
    assert result["both_boundaries_all_word_coverage_200ms"] == 0


def test_reject_wrong_source_and_overlapping_reference(bundle):
    audio, reference, evidence = bundle
    with pytest.raises(ValueError, match="source hash"):
        score(audio, reference, {**evidence, "audio_sha256": "0" * 64})
    reference["words"][1]["start"] = .39
    with pytest.raises(ValueError, match="nonoverlapping"):
        score(audio, reference, evidence)


def test_cli_emits_aggregate_only_and_stays_review_only(bundle, tmp_path, monkeypatch, capsys):
    audio, reference, evidence = bundle
    ref_file, asr_file = tmp_path / "ref.json", tmp_path / "asr.json"
    ref_file.write_text(json.dumps(reference), encoding="utf-8")
    asr_file.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["vpp", "speech-timing-benchmark", "--audio", str(audio),
                                   "--reference", str(ref_file), "--evidence", str(asr_file)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 3
    output = capsys.readouterr().out
    assert json.loads(output)["decision"] == "review_only"
    assert not any(value in output for value in ("fixture.wav", "lerne", _hash(audio)))
