import pytest

from vpp.consensus import compare_tracks
from vpp.extended_quality import (
    bilingual_review,
    pronunciation_review,
    scene_schedule,
    whisper_options,
    word_fingerprint,
)
from vpp.subtitle_sync import parse_srt


def test_fixed_whisper_configuration_and_fingerprint():
    opts = whisper_options()
    opts["temperature"] = 1
    assert whisper_options()["temperature"] == 0
    assert not whisper_options()["vad_filter"]
    assert word_fingerprint([{"word": "Haus", "start": 1}]) == word_fingerprint(
        [{"start": 1, "word": "Haus"}])
    assert word_fingerprint([{"word": "Haus", "start": 1}]) != word_fingerprint(
        [{"word": "Haus", "start": 2}])


def test_long_scene_coverage_and_uncovered_gaps():
    scenes = [{"id": "long", "start": 0, "end": 180}]
    points = scene_schedule(scenes, 180)[0]
    assert len(points) == 36
    assert points[0] == 2.5 and points[-1] == 177.5
    with pytest.raises(ValueError, match="Uncovered"):
        scene_schedule([{"id": "late", "start": 1, "end": 180}], 180)
    with pytest.raises(ValueError, match="Uncovered"):
        scene_schedule(scenes, 181)


@pytest.mark.parametrize("german,arabic,blocked", [
    ("Ich stelle eine Frage.", "أطرح سؤالًا.", False),
    ("Ich stelle eine frage.", "أطرح سؤالًا.", True),
    ("Ich stelle eine Frage.", "أجيب عن سؤال.", True),
    ("Ich stelle eine Frage.", "123", True),
])
def test_bilingual_teacher_reference(german, arabic, blocked):
    captions = parse_srt(f"1\n00:00:00,000 --> 00:00:02,000\n{german}\n{arabic}\n")
    report = bilingual_review(captions, [{"index": 1, "de": "Ich stelle eine Frage.",
                                         "ar": "أطرح سؤالًا."}])
    assert (report["decision"] == "blocked") is blocked
    assert not report["publication_approved"]


def test_phoneme_reference_localizes_german_contrast_and_accepts_variants():
    reference = {"audio_sha256": "a"*64, "annotation_source": "teacher",
                 "accepted_phones": [["ç"], ["x"]]}
    good = {"audio_sha256": "a"*64, "phones": ["ç"]}
    assert pronunciation_review(reference, good)["decision"] == "phone_sequence_consistent"
    report = pronunciation_review(reference, {**good, "phones": ["ʃ"]})
    assert report["decision"] == "needs_review"
    assert report["suspected_edits"][0]["observed"] == ["ʃ"]
    assert not report["publication_approved"]
    with pytest.raises(ValueError, match="same audio"):
        pronunciation_review(reference, {**good, "audio_sha256": "b"*64})


def test_unknown_model_cannot_create_independent_consensus():
    a = {"backend": "whisperx", "family": "whisper", "model": "test",
         "audio_sha256": "a"*64, "words": [{"word": "Haus", "start": 1, "end": 2}]}
    b = {**a, "backend": "invented", "family": "other"}
    report = compare_tracks([a, b], "a"*64)
    assert report["decision"] == "blocked"
    assert "unsupported_backend" in report["issues"]



def test_chunk_schedule_exact_ownership_and_context():
    from vpp.extended_quality import chunk_schedule

    chunks = chunk_schedule(65*16000)
    assert [(c["core_start"]//16000, c["core_end"]//16000) for c in chunks] == [
        (0, 30), (30, 60), (60, 65)]
    assert chunks[1]["decode_start"] == 25*16000
    assert chunks[1]["decode_end"] == 65*16000


def test_chunk_merge_never_shifts_or_duplicates_context_words():
    from vpp.extended_quality import chunk_schedule, own_chunk_words

    a, b = chunk_schedule(60*16000)
    first, invalid = own_chunk_words([{"word": "ein", "start": 29, "end": 29.5},
                                      {"word": "Haus", "start": 30, "end": 30.5}], a)
    second, other = own_chunk_words([{"word": "ein", "start": 4, "end": 4.5},
                                     {"word": "Haus", "start": 5, "end": 5.5},
                                     {"word": "unknown", "start": None}], b)
    assert [w["word"] for w in first+second] == ["ein", "Haus"]
    assert [w["start"] for w in first+second] == [29, 30]
    assert invalid == 0 and other == 1
