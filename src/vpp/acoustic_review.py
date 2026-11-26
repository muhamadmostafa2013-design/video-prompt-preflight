"""Source-bound review of independently recognized words, never a repair authorization."""
from __future__ import annotations

import csv
import json
from array import array
from pathlib import Path

from .acoustic_models import native_boundary
from .quality_evidence import _read_json
from .song_alignment import _hash, _number, _tokens
from .subtitle_sync import parse_srt


def _lex(text):
    return _tokens(text.replace("’", "'"))


def preserve_unaligned_words(text, words):
    """Retain recognized text when a forced-aligner drops or changes any words."""
    expected = _lex(text)
    if expected != [token for row in words for token in _lex(row["word"])]:
        return [{"word": token, "start": None, "end": None} for token in expected]
    return [{"word": row["word"], "start": native_boundary(row.get("start")),
             "end": native_boundary(row.get("end"))} for row in words]


def _distances(a, b):
    m = len(b)
    table = [array("H", range(m+1))]
    for i, word in enumerate(a, 1):
        prior = table[-1]
        row = array("H", [i])
        for j, other in enumerate(b, 1):
            row.append(min(row[-1]+1, prior[j]+1, prior[j-1]+(word != other)))
        table.append(row)
    return table


def unique_matches(expected, observed):
    """Only return equal-token matches shared by every optimal edit path."""
    n, m = len(expected), len(observed)
    if not 1 <= n <= 2000 or m > 2000:
        raise ValueError("Review supports 1..2000 reference and <=2000 observed tokens.")
    forward = _distances(expected, observed)
    reverse = _distances(expected[::-1], observed[::-1])
    cost = forward[n][m]
    results = []
    for i, word in enumerate(expected):
        candidates = []
        unmatched = False
        for j in range(m+1):
            before = forward[i][j]
            if before+1+reverse[n-i-1][m-j] == cost:
                unmatched = True
            if j < m and before+(word != observed[j])+reverse[n-i-1][m-j-1] == cost:
                if word == observed[j]:
                    candidates.append(j)
                else:
                    unmatched = True
        results.append({"candidates": candidates,
                        "unique": candidates[0] if len(candidates) == 1 and not unmatched else None})
    return cost, results


def review_evidence(audio, srt, evidence):
    """Reference timing is visual only; never use it to choose an acoustic match."""
    digest = _hash(Path(audio))
    if evidence.get("audio_sha256") != digest:
        raise ValueError("Audio SHA-256 differs from model report.")
    duration = evidence.get("source_duration_seconds", evidence.get("duration"))
    if not _number(duration) or not 0 < duration <= 1800:
        raise ValueError("Invalid evidence duration.")
    captions = parse_srt(Path(srt).read_text(encoding="utf-8-sig"))
    refs = [{"cue": cue["index"], "expected": token, "screen_start": cue["start_ms"]/1000,
             "screen_end": cue["end_ms"]/1000}
            for cue in captions for token in _lex(cue["lines"][0])]
    raw = evidence["words"]
    if not isinstance(raw, list) or len(raw) > 2000:
        raise ValueError("Invalid word track.")
    observed, invalid = [], []
    previous = 0.0
    for index, row in enumerate(raw, 1):
        if not isinstance(row, dict) or not isinstance(row.get("word"), str):
            raise TypeError("Malformed word record.")
        tokens = _lex(row["word"])
        start, end = row.get("start"), row.get("end")
        valid = (len(tokens) == 1 and _number(start) and _number(end)
                 and previous <= start < end <= duration)
        if not valid:
            invalid.append(index)
        if _number(start) and _number(end) and 0 <= start < end <= duration:
            previous = max(previous, end)
        for token in tokens:
            observed.append({"token": token, "raw_index": index, "start": start if valid else None,
                             "end": end if valid else None,
                             "probability": row.get("asr_probability", row.get("probability"))})
    errors, matches = unique_matches([r["expected"] for r in refs], [r["token"] for r in observed])
    rows, used = [], set()
    for ref, match in zip(refs, matches):
        index = match["unique"]
        if index is None:
            status = "ambiguous_repeat" if match["candidates"] else "unmatched_reference"
            rows.append({**ref, "status": status, "candidate_count": len(match["candidates"])})
            continue
        used.add(index)
        item = observed[index]
        status = "candidate_match" if item["start"] is not None else "invalid_timing"
        rows.append({**ref, "heard_candidate": item["token"], "start": item["start"],
                     "end": item["end"], "probability": item["probability"],
                     "raw_index": item["raw_index"], "status": status, "candidate_count": 1})
    extras = [{**item, "status": "unresolved_observation"} for i, item in enumerate(observed) if i not in used]
    return {"decision": "review_only" if observed else "blocked_empty_asr",
            "audio_sha256": digest, "reference_srt_sha256": _hash(Path(srt)),
            "reference_words": len(refs), "observed_words": len(observed),
            "word_errors": errors, "wer": errors/len(refs), "invalid_raw_indices": invalid,
            "candidate_matches": sum(row["status"] == "candidate_match" for row in rows),
            "rows": rows, "unresolved_observations": extras,
            "publication_approved": False, "human_listening_verified": False,
            "limitations": "Candidate matches only. Screen times are not acoustic ground truth. No subtitle repair."}


def _command(args):
    report = review_evidence(args.audio, args.srt, _read_json(args.evidence))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "acoustic-review.json").write_text(json.dumps(report, ensure_ascii=False,
        indent=2, allow_nan=False), encoding="utf-8")
    fields = ["cue", "expected", "screen_start", "screen_end", "heard_candidate", "start",
              "end", "probability", "raw_index", "status", "candidate_count"]
    with (output / "word-review.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report["rows"])
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "unresolved_observations")},
                     ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if report["decision"] == "blocked_empty_asr" else 3


def register(sub):
    parser = sub.add_parser("acoustic-review", help="Audit local ASR evidence against German SRT text")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.set_defaults(func=_command)
