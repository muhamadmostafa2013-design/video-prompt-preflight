"""Score local word boundaries against separate human annotations, not SRT cues."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .acoustic_review import _lex, unique_matches
from .quality_evidence import _read_json
from .song_alignment import _hash, _number

REFERENCE_SCHEMA = "vpp-human-word-boundaries-1"


def _word_rows(rows, duration, *, reference):
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError("Expected a list of up to 2000 word records.")
    output = []
    previous = 0.0
    invalid = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("word"), str):
            raise TypeError("Malformed benchmark word record.")
        tokens = _lex(row["word"])
        start, end = row.get("start"), row.get("end")
        interval = _number(start) and _number(end) and previous <= start < end <= duration
        valid = len(tokens) == 1 and interval
        if not valid:
            if reference:
                raise ValueError("Reference needs individually timed, ordered, nonoverlapping words.")
            invalid += 1
        if _number(start) and _number(end) and 0 <= start < end <= duration:
            previous = max(previous, end)
        output.extend((token, start if valid else None, end if valid else None) for token in tokens)
        if len(output) > 2000:
            raise ValueError("Benchmark supports at most 2000 normalized words.")
    return output, invalid


def _summary(errors):
    errors = sorted(errors)
    return {"mae_ms": round(sum(errors) / len(errors), 6) if errors else None,
            "p95_ms": errors[math.ceil(.95 * len(errors)) - 1] if errors else None}


def score(audio, reference, evidence):
    """Return aggregate-only metrics; timing never influences lexical matches."""
    if not isinstance(reference, dict) or reference.get("schema") != REFERENCE_SCHEMA:
        raise ValueError("Expected independent word annotations, not subtitles or ASR output.")
    if not isinstance(evidence, dict):
        raise TypeError("Expected one local ASR evidence object.")
    digest = _hash(Path(audio))
    if any(row.get("audio_sha256") != digest for row in (reference, evidence)):
        raise ValueError("The audio, annotations and ASR evidence must match the same source hash.")
    duration = evidence.get("source_duration_seconds", evidence.get("duration"))
    if not _number(duration) or not 0 < duration <= 1800:
        raise ValueError("Missing or invalid ASR source duration.")
    expected, _ = _word_rows(reference.get("words"), duration, reference=True)
    observed, invalid = _word_rows(evidence.get("words"), duration, reference=False)
    errors, matches = unique_matches([row[0] for row in expected], [row[0] for row in observed])
    onset_errors, offset_errors = [], []
    ambiguous = unmatched = invalid_matches = 0
    for (_, ref_start, ref_end), match in zip(expected, matches):
        if match["unique"] is None:
            if match["candidates"]:
                ambiguous += 1
            else:
                unmatched += 1
            continue
        _, start, end = observed[match["unique"]]
        if start is None:
            invalid_matches += 1
            continue
        onset_errors.append(round(abs(start - ref_start) * 1000, 6))
        offset_errors.append(round(abs(end - ref_end) * 1000, 6))

    n = len(expected)
    return {"schema": "vpp-speech-timing-benchmark-1", "reference_words": n,
            "observed_words": len(observed), "word_errors": errors, "wer": errors / n,
            "timed_unique_matches": len(onset_errors), "ambiguous_reference_words": ambiguous,
            "unmatched_reference_words": unmatched, "invalid_timing_reference_words": invalid_matches,
            "invalid_prediction_records": invalid,
            "both_boundaries_all_word_coverage_100ms": sum(
                max(a, b) <= 100 for a, b in zip(onset_errors, offset_errors)) / n,
            "both_boundaries_all_word_coverage_200ms": sum(
                max(a, b) <= 200 for a, b in zip(onset_errors, offset_errors)) / n,
            "matched_onset_only": _summary(onset_errors), "matched_offset_only": _summary(offset_errors),
            "decision": "review_only", "publication_approved": False,
            "limitations": "Annotation independence, audio rights, pronunciation and generalization are not verified."}


def _command(args):
    report = score(args.audio, _read_json(args.reference), _read_json(args.evidence))
    print(json.dumps(report, indent=2, allow_nan=False))
    return 3


def register(sub):
    parser = sub.add_parser("speech-timing-benchmark", help="Locally score ASR timing against human word boundaries")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--evidence", required=True)
    parser.set_defaults(func=_command)
