"""Conservative multi-model evidence comparison; no artificial agreement or approval."""
from __future__ import annotations

import math
import re
from pathlib import Path

from .quality_evidence import _read_json, _word_rows, benchmark_words
from .song_alignment import _hash, _number, _tokens


def compare_tracks(tracks, source_sha256, tolerance_ms=100):
    """Compare exact sequences and all timing boundaries; do not average timestamps."""
    if not isinstance(tracks, list):
        raise TypeError("Tracks must be a list.")
    if not 2 <= len(tracks) <= 5:
        raise ValueError("Require two to five model tracks.")
    if not isinstance(source_sha256, str) or not re.fullmatch("[a-f0-9]{64}", source_sha256):
        raise ValueError("Invalid source SHA-256.")
    if type(tolerance_ms) is not int or not 0 <= tolerance_ms <= 1000:
        raise ValueError("Tolerance must be 0..1000 ms.")
    ids = set()
    families = set()
    words = []
    issues = []
    invalid_tracks = []
    known_families = {"whisperx": "whisper", "faster-whisper": "whisper",
                      "wav2vec2-ctc": "wav2vec2"}
    for t in tracks:
        if not isinstance(t, dict):
            raise TypeError("Track must be an object.")
        backend, family = t.get("backend"), t.get("family")
        if (not isinstance(backend, str) or not backend.strip() or
                not isinstance(family, str) or not family.strip()):
            raise ValueError("Explicit backend and model family labels required.")
        identifier = (backend.casefold().strip(), str(t.get("model", "")).casefold().strip())
        if identifier in ids:
            issues.append("duplicate_model_track")
        ids.add(identifier)
        declared = family.casefold().strip()
        canonical = known_families.get(identifier[0], declared)
        if declared != canonical:
            issues.append("model_family_mismatch")
        families.add(canonical)
        if t.get("audio_sha256") != source_sha256:
            issues.append("source_hash_mismatch")
        try:
            parsed = _word_rows(t["words"], allow_empty=True)
            if t.get("timing_valid") is False:
                raise ValueError("Model reported invalid timing evidence.")
        except (ValueError, TypeError, KeyError):
            issues.append("invalid_word_timestamps")
            invalid_tracks.append({"backend": backend, "model": t.get("model")})
            parsed = None
        words.append(parsed)
    if len(families) < 2:
        issues.append("shared_model_family")
    if any(w == [] for w in words):
        issues.append("empty_track")
    comparisons = []
    if words[0]:
        for index, track in enumerate(tracks[1:], 1):
            if words[index] is None:
                continue
            result = benchmark_words(tracks[0]["words"], track["words"], tolerance_ms)
            comparisons.append({"backend": track["backend"], "model": track.get("model"),
                                "wer_vs_primary": result["wer"], "timing": result["timing"]})
    same_text = bool(words[0]) and all(t is not None and [w[0] for w in t] ==
                                       [w[0] for w in words[0]] for t in words)
    disagreements = []
    if not same_text:
        issues.append("word_sequence_disagrees")
    else:
        for i, rows in enumerate(zip(*words)):
            start_spread = round((max(r[1] for r in rows)-min(r[1] for r in rows))*1000, 6)
            end_spread = round((max(r[2] for r in rows)-min(r[2] for r in rows))*1000, 6)
            if max(start_spread, end_spread) > tolerance_ms:
                disagreements.append({"index": i+1, "word": rows[0][0],
                                      "primary_start": rows[0][1],
                                      "start_spread_ms": start_spread, "end_spread_ms": end_spread})
        if disagreements:
            issues.append("boundary_disagreement")
    return {"decision": "blocked" if issues else "review_agreement",
            "issues": sorted(set(issues)), "pairwise_vs_primary": comparisons,
            "disagreements": disagreements, "invalid_tracks": invalid_tracks,
            "distinct_declared_families": len(families),
            "primary_retained": True, "audio_sha256": source_sha256,
            "publication_approved": False, "human_listening_verified": False,
            "limitations": "Family labels and hashes are declared provenance, not proof of independence. Agreement is not ground truth."}


def phoneme_review(reference, observed):
    """Compare independently annotated phone sequences, not automatic pronunciation grading."""
    if not isinstance(reference, list) or not isinstance(observed, list):
        raise TypeError("Phone sequences must be lists.")
    if not reference or len(reference) > 2000 or len(observed) > 2000:
        raise ValueError("Nonempty phone reference and at most 2000 phones per sequence required.")
    for seq in (reference, observed):
        if any(not isinstance(p, str) or not p.strip() or len(p) > 20 for p in seq):
            raise ValueError("Each phone must be a short explicit IPA/phone label.")
    from .quality_evidence import _edit_distance
    errors = _edit_distance(reference, observed)
    return {"phone_errors": errors, "reference_phones": len(reference),
            "phone_error_rate": errors/len(reference), "decision": "review",
            "publication_approved": False,
            "limitations": "Supplied annotations only; no acoustic phoneme inference or accent grading."}


def audiovisual_review(captions, scenes, duration):
    """Verify alignment of required lexical cues with declared scene intervals."""
    if not _number(duration) or not 0 < duration <= 1800:
        raise ValueError("Invalid duration.")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 300:
        raise ValueError("Supply 1..300 scene intervals.")
    issues = []
    previous = 0.0
    ids = set()
    for s in scenes:
        sid, start, end = s["id"], s["start"], s["end"]
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError("Invalid or duplicate scene ID.")
        ids.add(sid)
        if not (_number(start) and _number(end) and previous <= start < end <= duration):
            raise ValueError("Scene intervals must be finite, ordered and nonoverlapping.")
        if start-previous > .05:
            issues.append({"scene": sid, "code": "timeline_gap"})
        previous = end
        required = s.get("required_phrases", [])
        if not isinstance(required, list) or any(not isinstance(p, str) or not _tokens(p) for p in required):
            raise ValueError("Invalid required phrase list.")
        if any(c["start_ms"] < 0 or c["end_ms"] > round(duration*1000)
               for c in captions):
            raise ValueError("Caption outside source duration.")
        inside = [c for c in captions if c["start_ms"] >= round(start*1000)-50 and
                  c["end_ms"] <= round(end*1000)+50]
        for phrase in required:
            wanted = " " + " ".join(_tokens(phrase)) + " "
            if not any(wanted in " " + " ".join(_tokens(c["lines"][0])) + " " for c in inside):
                issues.append({"scene": sid, "code": "required_phrase_outside_scene", "phrase": phrase})
    if duration-previous > .05:
        issues.append({"code": "timeline_end_uncovered"})
    return {"decision": "needs_review" if issues else "manifest_consistent",
            "issues": issues, "publication_approved": False,
            "limitations": "Checks declared scene timing and caption text only; not lip synchronization or actual scene semantics."}


def empirical_risk(records, category):
    """Observed failure rate and Wilson 95% interval; no predictive model claim."""
    if not isinstance(records, list) or len(records) > 100000:
        raise ValueError("Invalid benchmark records.")
    seen = set()
    outcomes = []
    for r in records:
        if not isinstance(r, dict):
            raise TypeError("Record must be an object.")
        ident = r["id"]
        if not isinstance(ident, str) or ident in seen or type(r["failed"]) is not bool:
            raise ValueError("Unique observation ID and boolean outcome required.")
        seen.add(ident)
        if r["category"] == category:
            outcomes.append(r["failed"])
    n = len(outcomes)
    if n < 30:
        return {"decision": "insufficient_data", "n": n, "category": category}
    p = sum(outcomes)/n
    z = 1.959963984540054
    denominator = 1+z*z/n
    center = (p+z*z/(2*n))/denominator
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return {"decision": "descriptive_only", "n": n, "category": category,
            "observed_failure_rate": p, "wilson_95": [max(0., center-half), min(1., center+half)],
            "limitations": "Requires representative independent trials. Not calibrated prediction of future generation failure."}


def load_tracks(audio, paths):
    return compare_tracks([_read_json(p) for p in paths], _hash(Path(audio)))
