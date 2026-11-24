"""Independent annotated benchmarks, explicit scene evidence, and local failure memory."""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

from .song_alignment import _hash, _number, _tokens

REGRESSIONS = {
    "subtitle_drift": "tests/test_subtitle_sync.py::test_nonuniform_drift_first_minute_and_repair",
    "missing_word": "tests/test_quality_engine.py::test_seeded_fault_injection",
    "repeat_missing": "tests/test_quality_engine.py::test_seeded_fault_injection",
    "low_score": "tests/test_quality_engine.py::test_seeded_fault_injection",
    "overlap": "tests/test_quality_engine.py::test_seeded_fault_injection",
    "wrong_caption": "tests/test_subtitle_sync.py::test_missing_extra_wrong_or_repeated_caption_blocks",
    "evidence_integrity": "tests/test_subtitle_sync.py::test_evidence_integrity",
    "audio_timeline": "tests/test_quality_engine.py::test_real_mux_with_synthetic_acoustic_evidence",
    "visual_review": "tests/test_quality_engine.py::test_real_visual_decode",
    "glossary_review": "tests/test_quality_engine.py::test_language_glossary_only",
}


def _read_json(path, limit=16_000_000):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Missing or oversized JSON file.")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON object key.")
            obj[key] = value
        return obj

    def invalid_constant(_value):
        raise ValueError("Non-finite JSON constant.")

    return json.loads(path.read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique, parse_constant=invalid_constant)


def _word_rows(rows, *, allow_empty=False):
    if not isinstance(rows, list):
        raise TypeError("Expected a word list.")
    if len(rows) > 2000 or (not rows and not allow_empty):
        raise ValueError("Benchmark requires a nonempty reference and at most 2000 words per track.")
    result = []
    previous = 0.0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("word"), str):
            raise TypeError("Malformed word record.")
        tokens = _tokens(row["word"])
        start, end = row.get("start"), row.get("end")
        if (len(tokens) != 1 or not _number(start) or not _number(end) or
                not previous <= start < end <= 1800):
            raise ValueError("Invalid, overlapping or non-monotonic word timestamps.")
        result.append((tokens[0], start, end))
        previous = end
    return result


def _edit_distance(a, b):
    previous = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(x != y)))
        previous = current
    return previous[-1]


def benchmark_words(reference, prediction, tolerance_ms=150):
    """Compare machine timestamps with independent, supplied reference labels."""
    if type(tolerance_ms) is not int or not 0 <= tolerance_ms <= 1000:
        raise ValueError("Tolerance must be 0..1000 ms.")
    ref, pred = _word_rows(reference), _word_rows(prediction, allow_empty=True)
    expected, observed = [x[0] for x in ref], [x[0] for x in pred]
    distance = _edit_distance(expected, observed)
    result = {"reference_words": len(ref), "predicted_words": len(pred),
              "word_edit_distance": distance, "wer": round(distance / len(ref), 6),
              "tolerance_ms": tolerance_ms, "timing": None, "decision": "review",
              "publication_approved": False,
              "basis": "supplied reference labels; their accuracy and independence are not certified"}
    # Don't silently align mismatched or repeated word sequences.
    if expected != observed:
        result["decision"] = "text_mismatch"
        return result
    boundaries = [abs(round((p[k]-r[k])*1000, 6)) for r, p in zip(ref, pred) for k in (1, 2)]
    starts = [round((p[1]-r[1])*1000, 6) for r, p in zip(ref, pred)]
    errors = sorted(boundaries)
    result["timing"] = {"mae_ms": round(sum(errors)/len(errors), 3),
                        "p95_ms": errors[math.ceil(.95*len(errors))-1],
                        "max_ms": max(errors),
                        "fraction_within_tolerance": sum(x <= tolerance_ms for x in errors)/len(errors),
                        "late_starts": sum(x > tolerance_ms for x in starts),
                        "early_starts": sum(x < -tolerance_ms for x in starts)}
    return result


def scene_review(expected, observed, duration):
    """Check explicit human observation tags, not automatic visual recognition."""
    if not _number(duration) or not 0 < duration <= 1800:
        raise ValueError("Duration must be positive and <=1800 seconds.")
    if not isinstance(expected, list) or not isinstance(observed, list):
        raise TypeError("Scene manifests must be lists.")
    if not expected or len(expected) > 300 or len(observed) > 300:
        raise ValueError("Expected manifest needs 1..300 scenes; observed max 300.")
    issues = []
    last_end = 0.0
    seen = set()
    actual = {}
    for row in observed:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or
                not isinstance(row.get("tags"), list) or any(not isinstance(t, str) for t in row["tags"])):
            raise ValueError("Malformed observed scene.")
        if row["id"] in actual:
            raise ValueError("Duplicate observation ID.")
        actual[row["id"]] = row
    for row in expected:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise TypeError("Malformed expected scene.")
        sid = row["id"]
        tags, banned = row.get("required_tags", []), row.get("forbidden_tags", [])
        if (sid in seen or not isinstance(tags, list) or not isinstance(banned, list) or
                any(not isinstance(t, str) or not t.strip() for t in tags+banned)):
            raise ValueError("Duplicate scene or invalid scene tags.")
        seen.add(sid)
        start, end = row.get("start"), row.get("end")
        if not (_number(start) and _number(end) and 0 <= start < end <= duration):
            raise ValueError("Invalid scene interval.")
        if abs(start-last_end) > .05:
            issues.append({"scene": sid, "code": "timeline_gap_or_overlap"})
        last_end = end
        obs = actual.get(sid)
        if obs is None:
            issues.append({"scene": sid, "code": "missing_observation"})
            continue
        if not (_number(obs.get("start")) and _number(obs.get("end")) and
                0 <= obs["start"] < obs["end"] <= duration):
            raise ValueError("Invalid observed interval.")
        if abs(obs["start"]-start) > .15 or abs(obs["end"]-end) > .15:
            issues.append({"scene": sid, "code": "observed_timing_differs"})
        for tag in sorted(set(tags)-set(obs["tags"])):
            issues.append({"scene": sid, "code": "required_tag_missing", "tag": tag})
        for tag in sorted(set(banned)&set(obs["tags"])):
            issues.append({"scene": sid, "code": "forbidden_tag_observed", "tag": tag})
    if abs(last_end-duration) > .05:
        issues.append({"code": "timeline_end_uncovered"})
    for sid in sorted(set(actual)-seen):
        issues.append({"scene": sid, "code": "unexpected_scene"})
    return {"decision": "needs_review" if issues else "manifest_consistent",
            "issues": issues, "publication_approved": False,
            "basis": "reviewer-supplied tags; not automatic identity, safety or scene recognition"}


def failure_memory(path, code=None):
    """Store only enumerated failure categories and counts; never raw prompts/media."""
    path = Path(path)
    state = _read_json(path, 100000) if path.exists() else {"schema": 1, "counts": {}}
    if not isinstance(state, dict) or state.get("schema") != 1 or not isinstance(state.get("counts"), dict):
        raise ValueError("Invalid failure memory schema.")
    counts = state["counts"]
    if any(k not in REGRESSIONS or type(v) is not int or not 0 <= v <= 1000000 for k, v in counts.items()):
        raise ValueError("Invalid failure memory entries.")
    if code is not None:
        if code not in REGRESSIONS or counts.get(code, 0) >= 1000000:
            raise ValueError("Unknown or exhausted regression category.")
        counts[code] = counts.get(code, 0)+1
        path.parent.mkdir(parents=True, exist_ok=True)
        # Single-writer local workflow. Atomic replacement avoids partial JSON on interruption.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".vpp-memory-", delete=False) as handle:
            tmp = Path(handle.name)
            json.dump({"schema": 1, "counts": counts}, handle, indent=2, sort_keys=True)
        try:
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    return {"priorities": [{"category": k, "count": counts[k], "regression": REGRESSIONS[k]}
                           for k in sorted(counts, key=lambda k: (-counts[k], k))],
            "auto_changes_rules": False, "privacy": "local aggregate codes/counts only"}


def _print(result):
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


def _benchmark(args):
    reference = _read_json(args.reference)
    prediction = _read_json(args.prediction)
    source_hash = _hash(Path(args.audio))
    if reference.get("audio_sha256") != source_hash or prediction.get("audio_sha256") != source_hash:
        raise ValueError("Reference/prediction must identify the same source audio.")
    if reference.get("annotation_source") != "human":
        raise ValueError("Independent human annotation label is required.")
    _print(benchmark_words(reference["words"], prediction["words"], args.tolerance_ms))
    return 3


def _scenes(args):
    _print(scene_review(_read_json(args.expected), _read_json(args.observed), args.duration))
    return 3


def _memory(args):
    _print(failure_memory(args.file, args.record))
    return 0


def register(sub):
    bench = sub.add_parser("benchmark-alignment", help="Measure machine words against supplied human annotations")
    bench.add_argument("--audio", required=True)
    bench.add_argument("--reference", required=True)
    bench.add_argument("--prediction", required=True)
    bench.add_argument("--tolerance-ms", type=int, default=150)
    bench.set_defaults(func=_benchmark)
    scene = sub.add_parser("scene-review", help="Compare expected timeline with supplied visual observations")
    scene.add_argument("--expected", required=True)
    scene.add_argument("--observed", required=True)
    scene.add_argument("--duration", required=True, type=float)
    scene.set_defaults(func=_scenes)
    memory = sub.add_parser("failure-memory", help="Local category counts mapped to regression tests")
    memory.add_argument("--file", required=True)
    memory.add_argument("--record", choices=sorted(REGRESSIONS))
    memory.set_defaults(func=_memory)
