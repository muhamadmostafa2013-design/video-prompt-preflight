"""Independent singing benchmark: word onsets, not inferred word endings."""
from __future__ import annotations

import math
from array import array

from .song_alignment import _number, _tokens


def onset_benchmark(reference, prediction, duration):
    """Deterministic edit alignment; missing/substituted words count against coverage."""
    if not _number(duration) or not 0 < duration <= 1800:
        raise ValueError("Invalid source duration.")
    if not isinstance(reference, list) or not isinstance(prediction, list):
        raise TypeError("Expected word lists.")
    if not 1 <= len(reference) <= 2000 or len(prediction) > 2000:
        raise ValueError("Benchmark supports up to 2000 words per track.")
    ref, pred = [], []
    previous = -1.0
    for word in reference:
        tokens = _tokens(word["word"])
        onset = word["start"]
        if not tokens or not _number(onset) or not previous <= onset < duration or onset < 0:
            raise ValueError("Invalid independent reference onset.")
        # Multiple normalized tokens in a reference record share the supplied onset;
        # reject instead of inventing individual word times.
        if len(tokens) != 1:
            raise ValueError("Reference records must be individual normalized words.")
        ref.append((tokens[0], onset))
        previous = onset
    previous = -1.0
    invalid = 0
    for word in prediction:
        tokens = _tokens(word["word"])
        onset = word.get("start")
        valid = _number(onset) and 0 <= onset < duration and onset >= previous
        if valid:
            previous = onset
        if len(tokens) != 1 or not valid:
            invalid += 1
        for token in tokens:
            pred.append((token, onset if valid and len(tokens) == 1 else None))
    if len(pred) > 2000:
        raise ValueError("Too many normalized prediction words.")
    # Unit-cost Levenshtein DP. Text-only alignment, never optimized by timestamps.
    n, m = len(ref), len(pred)
    dp = [array("H", range(m+1))]
    for i in range(1, n+1):
        row = array("H", [i])
        for j in range(1, m+1):
            row.append(min(row[j-1]+1, dp[-1][j]+1,
                           dp[-1][j-1]+(ref[i-1][0] != pred[j-1][0])))
        dp.append(row)
    i, j = n, m
    matched = 0
    errors = []
    while i or j:
        if i and j and dp[i][j] == dp[i-1][j-1]+(ref[i-1][0] != pred[j-1][0]):
            if ref[i-1][0] == pred[j-1][0]:
                matched += 1
                if pred[j-1][1] is not None:
                    errors.append(abs(round((ref[i-1][1]-pred[j-1][1])*1000, 6)))
            i -= 1
            j -= 1
        elif i and dp[i][j] == dp[i-1][j]+1:
            i -= 1
        else:
            j -= 1
    errors.sort()
    hits100 = sum(e <= 100 for e in errors)
    hits200 = sum(e <= 200 for e in errors)
    return {"reference_words": n, "predicted_words": m, "word_errors": dp[n][m],
            "wer": dp[n][m]/n, "matched_words": matched, "timed_matches": len(errors),
            "invalid_prediction_records": invalid, "within_100ms": hits100,
            "within_200ms": hits200, "all_word_coverage_100ms": hits100/n,
            "all_word_coverage_200ms": hits200/n,
            "matched_onset_mae_ms": sum(errors)/len(errors) if errors else None,
            "matched_onset_p95_ms": errors[math.ceil(.95*len(errors))-1] if errors else None,
            "publication_approved": False,
            "limitations": "Onsets only; repeated lyrics can make text-only edit alignment ambiguous. Matched-word error is conditional; all-word coverage penalizes missing words."}
