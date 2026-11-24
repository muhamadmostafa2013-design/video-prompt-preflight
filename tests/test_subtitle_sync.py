import argparse
import json

import pytest

from vpp.song_alignment import _hash
from vpp.subtitle_sync import audit_sync, parse_srt, repair_srt, run_sync

LYRICS = ["Ein Nomen, ein Verb!", "Ein Nomen, ein Verb!"]
WORDS = [
    {"word": word, "start": start, "end": end, "score": .9}
    for word, start, end in [
        ("Ein", 10.0, 10.3), ("Nomen", 10.3, 10.9),
        ("ein", 11.0, 11.2), ("Verb!", 11.2, 11.7),
        ("Ein", 80.0, 80.3), ("Nomen", 80.3, 80.9),
        ("ein", 81.0, 81.2), ("Verb!", 81.2, 81.7),
    ]
]
SRT = """1
00:00:11,300 --> 00:00:12,500
Ein Nomen,
اسم

2
00:00:12,000 --> 00:00:13,000
ein Verb!
وفعل

3
00:01:19,500 --> 00:01:22,000
Ein Nomen, ein Verb!
اسم وفعل
"""


def test_nonuniform_drift_first_minute_and_repair():
    captions = parse_srt(SRT)
    report = audit_sync(captions, LYRICS, WORDS, 90)
    assert report["timing_status"] == "needs_repair"
    assert [r["start_delta_ms"] for r in report["rows"]] == [1300, 1000, -500]
    assert report["first_60_seconds"]["count"] == 2
    assert report["first_60_seconds"]["late_starts"] == 2
    assert report["metrics"]["early_starts"] == 1
    assert report["original_overlapping_cues"] == [2]
    assert report["metrics"]["max_absolute_ms"] == 1600
    repaired = parse_srt(repair_srt(captions, report))
    assert [r["lines"] for r in repaired] == [r["lines"] for r in captions]
    assert repaired[0]["start_ms"] == 10000
    result = audit_sync(repaired, LYRICS, WORDS, 90)
    assert result["timing_status"] == "within_tolerance"
    assert result["metrics"]["max_absolute_ms"] == 0
    assert not result["publication_approved"]
    assert not result["human_listening_verified"]


@pytest.mark.parametrize("old", [
    SRT.replace("ein Verb!", "eine Frage!", 1),
    SRT.split("\n\n3\n")[0],
    SRT.replace("Ein Nomen,", "Ein Nomen, Ein Nomen,", 1),
])
def test_missing_extra_wrong_or_repeated_caption_blocks(old):
    captions = parse_srt(old)
    report = audit_sync(captions, LYRICS, WORDS, 90)
    assert report["decision"] == "blocked"
    assert report["text_differences"]
    with pytest.raises(ValueError):
        repair_srt(captions, report)


@pytest.mark.parametrize("words", [
    [], WORDS[:-1], [{**WORDS[0], "score": .1}, *WORDS[1:]],
    [{**WORDS[0], "start": float("nan")}, *WORDS[1:]],
    [{**WORDS[0], "end": 15}, *WORDS[1:]],
])
def test_bad_acoustic_evidence_blocks(words):
    assert audit_sync(parse_srt(SRT), LYRICS, words, 90)["decision"] == "blocked"


@pytest.mark.parametrize("invalid", [
    "", SRT.replace("00:00:11,300", "00:00:61,300"),
    SRT.replace("00:00:12,500", "00:00:11,300"),
    SRT.replace("Ein Nomen,", "<b>Ein Nomen,</b>", 1),
    SRT.replace("\n2\n", "\n9\n"),
])
def test_invalid_srt(invalid):
    with pytest.raises(ValueError):
        parse_srt(invalid)


def test_utf8_bom_crlf():
    assert parse_srt("\ufeff" + SRT.replace("\n", "\r\n")) == parse_srt(SRT)


def fixture(tmp_path):
    audio = tmp_path / "source.mp3"
    audio.write_bytes(b"synthetic source identity; not actual audio")
    lyrics = tmp_path / "lyrics.txt"
    lyrics.write_text("\n".join(LYRICS), encoding="utf-8")
    srt = tmp_path / "old.srt"
    srt.write_text(SRT, encoding="utf-8")
    run = tmp_path / "align"
    (run / "asr").mkdir(parents=True)
    raw = run / "asr" / "vocals.json"
    raw.write_text(json.dumps({"word_segments": WORDS}))
    (run / "alignment_report.json").write_text(json.dumps({
        "decision": "review", "evidence_schema": "vpp.whisperx.words.v1",
        "audio_sha256": _hash(audio), "reference_sha256": _hash(lyrics),
        "word_evidence_sha256": _hash(raw), "duration_seconds": 90, "min_score": .5,
    }))
    args = argparse.Namespace(srt=srt, audio=audio, lyrics=lyrics, alignment_run=run,
                              output=tmp_path / "out", tolerance_ms=150, min_score=.5, repair=True)
    return args, raw


def test_cli_workflow_preserves_original_and_rechecks(tmp_path):
    args, _ = fixture(tmp_path)
    original = args.srt.read_bytes()
    assert run_sync(args) == 3
    assert args.srt.read_bytes() == original
    report = json.loads((args.output / "subtitle_sync_report.json").read_text())
    assert report["repair_written"]
    assert report["post_repair_metrics"]["max_absolute_ms"] == 0
    assert (args.output / "REPAIRED_DRAFT_REQUIRES_LISTENING.srt").is_file()


@pytest.mark.parametrize("changed", ["audio", "lyrics", "raw"])
def test_evidence_integrity(tmp_path, changed):
    args, raw = fixture(tmp_path)
    path = raw if changed == "raw" else getattr(args, changed)
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="integrity mismatch"):
        run_sync(args)
    assert not args.output.exists()
