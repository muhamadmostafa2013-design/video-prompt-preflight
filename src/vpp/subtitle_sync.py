"""Compare bilingual SRT line boundaries to local acoustic word evidence.

All measurements are relative to model evidence, not human-certified ground truth.
Never interpolate missing words or overwrite original captions.
"""
from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path

from .quality_evidence import _read_json
from .song_alignment import (
    _hash,
    _number,
    _stamp,
    _tokens,
    _written_tokens,
    audit_words,
)

_TIMING = re.compile(
    r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})[ \t]+-->[ \t]+"
    r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
)
_MAX_TEXT = 2_000_000
_MAX_EVIDENCE = 32_000_000
_MAX_WORDS = 20_000


def _ms(parts):
    h, m, s, ms = map(int, parts)
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def parse_srt(text):
    """Strict UTF-8 SRT; German is the first text line; translations follow."""
    if not isinstance(text, str):
        raise TypeError("SRT must be text.")
    if len(text) > _MAX_TEXT:
        raise ValueError("Oversized SRT.")
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("Empty SRT.")
    result = []
    for i, block in enumerate(re.split(r"\n[ \t]*\n+", text), 1):
        lines = block.split("\n")
        if len(lines) < 3 or lines[0].strip() != str(i):
            raise ValueError(f"Cue {i}: expected sequential index, timestamp and text.")
        match = _TIMING.fullmatch(lines[1].strip())
        if match is None:
            raise ValueError(f"Cue {i}: invalid SRT timestamp.")
        start, end = _ms(match.groups()[:4]), _ms(match.groups()[4:])
        if start >= end:
            raise ValueError(f"Cue {i}: nonpositive duration.")
        content = lines[2:]
        if any(not line.strip() or "<" in line or ">" in line or "\x00" in line
               for line in content) or not _tokens(content[0]):
            raise ValueError(f"Cue {i}: plain nonempty text required; German must be first.")
        result.append({"index": i, "start_ms": start, "end_ms": end, "lines": content})
    return result


def _metrics(rows, tolerance):
    if not rows:
        return {"count": 0}
    start = [abs(row["start_delta_ms"]) for row in rows]
    end = [abs(row["end_delta_ms"]) for row in rows]
    errors = sorted(start + end)
    return {
        "count": len(rows),
        "start_mae_ms": round(sum(start) / len(start), 2),
        "end_mae_ms": round(sum(end) / len(end), 2),
        "boundary_p95_absolute_ms": errors[math.ceil(.95 * len(errors)) - 1],
        "max_absolute_ms": max(errors),
        "late_starts": sum(row["start_delta_ms"] > tolerance for row in rows),
        "early_starts": sum(row["start_delta_ms"] < -tolerance for row in rows),
        "within_tolerance": sum(max(abs(row["start_delta_ms"]), abs(row["end_delta_ms"]))
                                <= tolerance for row in rows),
    }


def _changes(expected, observed):
    # Bounded diagnostics: exact equality remains the actual gate.
    if len(expected) + len(observed) > 4000:
        return [{"kind": "mismatch", "reason": "Long transcript; inspect raw word evidence."}]
    matcher = difflib.SequenceMatcher(None, expected, observed, autojunk=False)
    return [{"kind": tag, "reference_word_index": a + 1,
             "expected": expected[a:b][:30], "observed": observed[c:d][:30]}
            for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal"][:50]


def audit_sync(captions, reference_lines, words, duration, *, min_score=.5, tolerance_ms=150):
    """Re-segment validated words by caption boundaries, preserving caption text."""
    if type(tolerance_ms) is not int or not 0 <= tolerance_ms <= 1000:
        raise ValueError("Tolerance must be 0..1000 ms.")
    if not isinstance(words, list):
        raise TypeError("Word evidence must be a list.")
    if len(words) > _MAX_WORDS:
        raise ValueError("Oversized word evidence.")
    if not isinstance(captions, list):
        raise TypeError("Captions must be a list.")
    if not captions:
        raise ValueError("At least one parsed SRT cue is required.")
    report = {
        "decision": "blocked", "timing_status": "unverified", "issues": [],
        "human_listening_verified": False, "publication_approved": False,
        "basis": "machine acoustic word evidence; not human ground truth",
        "tolerance_ms": tolerance_ms, "rows": [], "metrics": {}, "first_60_seconds": {},
    }
    validated = audit_words(reference_lines, words, duration, min_score)
    if validated["decision"] != "review":
        report["issues"].extend(validated["issues"])
        return report
    # Compare written German exactly in case, unlike the ASR transcript.
    expected = [token for line in reference_lines for token in _written_tokens(line)]
    observed = [token for cue in captions for token in _written_tokens(cue["lines"][0])]
    if expected != observed:
        report["issues"].append("Caption German differs from validated reference; no automatic rewrite.")
        report["text_differences"] = _changes(expected, observed)
        return report

    offset = 0
    previous_end = 0
    original_overlaps = []
    out_of_bounds = []
    for cue in captions:
        count = len(_tokens(cue["lines"][0]))
        span = words[offset:offset + count]
        start, end = round(span[0]["start"] * 1000), round(span[-1]["end"] * 1000)
        if start >= end:
            report["issues"].append(f"Cue {cue['index']}: timing collapses after millisecond rounding.")
            return report
        if cue["start_ms"] < previous_end:
            original_overlaps.append(cue["index"])
        previous_end = max(previous_end, cue["end_ms"])
        if cue["end_ms"] > round(duration * 1000):
            out_of_bounds.append(cue["index"])
        start_delta = cue["start_ms"] - start
        end_delta = cue["end_ms"] - end
        report["rows"].append({
            "index": cue["index"], "text": cue["lines"][0],
            "original_start_ms": cue["start_ms"], "original_end_ms": cue["end_ms"],
            "acoustic_start_ms": start, "acoustic_end_ms": end,
            "start_delta_ms": start_delta, "end_delta_ms": end_delta,
            "start_status": "late" if start_delta > tolerance_ms else
                            "early" if start_delta < -tolerance_ms else "within_tolerance",
            "word_count": count, "min_alignment_score": min(w["score"] for w in span),
        })
        offset += count

    rows = report["rows"]
    report["metrics"] = _metrics(rows, tolerance_ms)
    report["first_60_seconds"] = _metrics([r for r in rows if r["acoustic_start_ms"] < 60000],
                                          tolerance_ms)
    report["original_overlapping_cues"] = original_overlaps
    report["original_out_of_bounds_cues"] = out_of_bounds
    report["decision"] = "review"
    report["timing_status"] = ("within_tolerance" if not original_overlaps and not out_of_bounds
                               and report["metrics"]["within_tolerance"] == len(rows)
                               else "needs_repair")
    return report


def repair_srt(captions, report):
    """Return a separate draft, changing timestamps only."""
    if report["decision"] != "review" or len(report["rows"]) != len(captions):
        raise ValueError("Repair blocked: incomplete acoustic evidence.")
    blocks = []
    previous_end = 0
    for cue, row in zip(captions, report["rows"]):
        start, end = row["acoustic_start_ms"], row["acoustic_end_ms"]
        if cue["index"] != row["index"] or cue["lines"][0] != row["text"]:
            raise ValueError("Repair blocked: caption/report mismatch.")
        if not (previous_end <= start < end):
            raise ValueError("Repair blocked: rounded cue overlap or invalid interval.")
        previous_end = end
        blocks.append(f"{cue['index']}\n{_stamp(start/1000)} --> {_stamp(end/1000)}\n"
                      + "\n".join(cue["lines"]))
    return "\n\n".join(blocks) + "\n"


def _read(path, limit):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Missing or oversized input file.")
    return path.read_text(encoding="utf-8-sig")


def load_evidence(audio, lyrics, run):
    """Bind evidence to the source recording/reference and detect file changes."""
    run = Path(run)
    metadata = _read_json(run / "alignment_report.json", _MAX_EVIDENCE)
    raw_path = run / "asr" / "vocals.json"
    if (metadata.get("decision") != "review" or
            metadata.get("evidence_schema") != "vpp.whisperx.words.v1"):
        raise ValueError("A complete, current align-song run is required; no guessed timing.")
    for path, key in [(audio, "audio_sha256"), (lyrics, "reference_sha256"),
                      (raw_path, "word_evidence_sha256")]:
        if metadata.get(key) != _hash(Path(path)):
            raise ValueError(f"Evidence integrity mismatch: {key}.")
    duration, score = metadata.get("duration_seconds"), metadata.get("min_score")
    if not _number(duration) or not 0 < duration <= 1800 or not _number(score) or not 0 <= score <= 1:
        raise ValueError("Invalid acoustic evidence metadata.")
    raw = _read_json(raw_path, _MAX_EVIDENCE)
    return raw.get("word_segments", []), duration, score


def run_sync(args):
    captions = parse_srt(_read(args.srt, _MAX_TEXT))
    lines = [line.strip() for line in _read(args.lyrics, _MAX_TEXT).splitlines() if line.strip()]
    words, duration, score = load_evidence(args.audio, args.lyrics, args.alignment_run)
    if not _number(args.min_score) or not 0 <= args.min_score <= 1:
        raise ValueError("min_score must be finite and in [0, 1].")
    report = audit_sync(captions, lines, words, duration,
                        min_score=max(score, args.min_score), tolerance_ms=args.tolerance_ms)
    report["source_audio_sha256"] = _hash(Path(args.audio))
    report["source_srt_sha256"] = _hash(Path(args.srt))
    report["repair_written"] = False
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    if args.repair and report["decision"] == "review":
        draft = repair_srt(captions, report)
        repaired = parse_srt(draft)
        recheck = audit_sync(repaired, lines, words, duration,
                             min_score=max(score, args.min_score), tolerance_ms=args.tolerance_ms)
        if (recheck["timing_status"] != "within_tolerance" or
                recheck["metrics"]["max_absolute_ms"] != 0 or
                [c["lines"] for c in repaired] != [c["lines"] for c in captions]):
            raise ValueError("Internal repair validation failed.")
        (output / "REPAIRED_DRAFT_REQUIRES_LISTENING.srt").write_text(draft, encoding="utf-8")
        report["repair_written"] = True
        report["post_repair_metrics"] = recheck["metrics"]
    (output / "subtitle_sync_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if report["decision"] == "blocked" else 3


def register(sub):
    p = sub.add_parser("subtitle-sync", help="Audit/repair SRT against local align-song evidence")
    p.add_argument("srt", help="Existing plain SRT (German first line; translations below)")
    p.add_argument("--audio", required=True, help="Same original audio used for alignment")
    p.add_argument("--lyrics", required=True, help="Same exact lyric reference")
    p.add_argument("--alignment-run", required=True, help="Complete align-song output directory")
    p.add_argument("-o", "--output", required=True, help="New output directory")
    p.add_argument("--tolerance-ms", type=int, default=150)
    p.add_argument("--min-score", type=float, default=.5)
    p.add_argument("--repair", action="store_true", help="Write separate corrected draft and recheck")
    p.set_defaults(func=run_sync)
