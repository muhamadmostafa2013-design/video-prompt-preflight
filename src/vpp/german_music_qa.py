"""Deterministic, local-first preflight for German educational songs.

This module checks prompt/spec consistency; it does NOT listen to generated audio
or certify grammar, CEFR levels, melody originality, or pronunciation.
"""
from __future__ import annotations

import re
from typing import Any

KNOWN_ARTICLES = {
    "hund": "der", "katze": "die", "pferd": "das",
    "vogel": "der", "fisch": "der", "maus": "die",
    "elefant": "der", "hase": "der", "löwe": "der",
    "tiger": "der", "kuh": "die", "schaf": "das",
    "kaninchen": "das", "bär": "der", "ente": "die",
    "frosch": "der", "apfel": "der", "banane": "die",
    "brot": "das", "haus": "das", "schule": "die",
    "buch": "das", "tisch": "der", "stuhl": "der",
}
ARTICLES = {"der", "die", "das"}
LEVELS = {"pre-a1", "a1", "a2", "b1", "b2", "c1", "c2"}
ARABIC = re.compile(r"[\u0600-\u06ff]")
MAX_LYRICS = 16000
MAX_TARGETS = 50


def _phrase_count(lyrics: str, phrase: str) -> int:
    pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, phrase.split())) + r"(?!\w)"
    return len(re.findall(pattern, lyrics, flags=re.IGNORECASE))


def _checked_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise TypeError("Song spec must be a YAML/JSON object.")
    if not isinstance(spec.get("lyrics"), str):
        raise TypeError("lyrics must be a string.")
    if len(spec["lyrics"]) > MAX_LYRICS:
        raise ValueError("lyrics exceed the 16000-character local QA limit.")
    vocabulary = spec.get("target_vocabulary", [])
    if not isinstance(vocabulary, list) or len(vocabulary) > MAX_TARGETS:
        raise ValueError("target_vocabulary must be a list of at most 50 phrases.")
    if any(not isinstance(v, str) or not v.strip() or len(v) > 120 for v in vocabulary):
        raise ValueError("Every target_vocabulary phrase must be a nonempty string (max 120 characters).")
    age = spec.get("age_range", [6, 9])
    if (not isinstance(age, list) or len(age) != 2 or
            any(type(v) is not int or not 0 <= v <= 100 for v in age) or age[0] > age[1]):
        raise ValueError("age_range must be [minimum_age, maximum_age].")
    for field in ("bpm", "duration_seconds", "min_repetitions", "max_words_per_line"):
        if field in spec and (type(spec[field]) not in (int, float) or
                              not 0 < spec[field] <= 10000):
            raise ValueError(f"{field} must be a positive finite number.")
    for field in ("allow_bilingual", "instrumental_only"):
        if field in spec and not isinstance(spec[field], bool):
            raise ValueError(f"{field} must be a boolean.")
    for field in ("title", "style", "vocal_direction", "provider", "language", "cefr"):
        if field in spec and (not isinstance(spec[field], str) or len(spec[field]) > 500):
            raise ValueError(f"{field} must be a short string.")
    return spec


def review_song(spec: dict[str, Any]) -> dict[str, Any]:
    """Return blocking, advisory and manually verifiable song-preflight findings."""
    spec = _checked_spec(spec)
    lyrics = spec["lyrics"].strip()
    findings: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    def add(rule: str, severity: str, message: str, points: int = 0) -> None:
        findings.append({
            "rule_id": rule, "severity": severity, "message": message, "points": points
        })

    language = spec.get("language", "de").lower()
    cefr = spec.get("cefr", "A1")
    age_min, _age_max = spec.get("age_range", [6, 9])
    repetitions = spec.get("min_repetitions", 2)
    words_per_line = spec.get("max_words_per_line", 12)
    bpm = spec.get("bpm", None)
    targets = spec.get("target_vocabulary", [])

    if not lyrics:
        add("music.lyrics.empty", "error", "Add the exact German lyrics.", 40)
    if language != "de":
        add("music.language.unsupported", "warning",
            "This ruleset focuses on German (language: de). Other languages require human review.", 12)
    if cefr.lower() not in LEVELS:
        add("music.cefr.unknown", "warning", "Use a recognized CEFR level and validate pedagogical fit.", 8)
    if not spec.get("allow_bilingual", False) and ARABIC.search(lyrics):
        add("music.lyrics.arabic", "error",
            "Arabic-script text in German-only lyrics; enable allow_bilingual if intentional.", 30)
    if spec.get("instrumental_only", False) and lyrics:
        add("music.vocals.conflict", "error",
            "instrumental_only conflicts with requested sung lyrics.", 30)
    if repetitions != int(repetitions) or repetitions > 20:
        add("music.repetition.invalid", "error", "Use a whole min_repetitions value from 1 to 20.", 20)

    if bpm is None:
        add("music.bpm.missing", "warning", "Set a tempo (BPM) for predictable educational pacing.", 5)
    elif not 45 <= bpm <= 200:
        add("music.bpm.extreme", "warning",
            "Very slow/fast tempo: verify articulation and age suitability.", 8)
    if age_min <= 9 and bpm is not None and bpm > 150:
        add("music.tempo.children", "warning",
            "For young learners, a fast beat may obscure consonants and articles.", 8)
    if not targets:
        add("music.targets.missing", "warning",
            "Define target_vocabulary to verify that every teaching objective appears.", 10)

    for target in targets:
        phrase = " ".join(target.split())
        count = _phrase_count(lyrics, phrase)
        counts[target] = count
        if count == 0:
            add("music.target.missing", "error", f"Required vocabulary not found: {target}", 25)
        elif repetitions == int(repetitions) and count < repetitions:
            add("music.target.repetition", "warning",
                f"{target}: {count} occurrence(s); requested minimum {int(repetitions)}.", 9)

    # Restricted lexicon: do not infer that unknown nouns or all grammar are correct.
    seen: set[tuple[str, str]] = set()
    for article, noun in re.findall(r"(?<!\w)(der|die|das)\s+([\wÄÖÜäöüß]+)\b",
                                    lyrics, flags=re.IGNORECASE):
        expected = KNOWN_ARTICLES.get(noun.casefold())
        if expected is not None and article.casefold() != expected:
            item = (article.casefold(), noun.casefold())
            if item not in seen:
                seen.add(item)
                add("music.article.mismatch", "error",
                    f"Check '{article} {noun}': expected '{expected} {noun}' for this noun.", 35)

    if age_min <= 9:
        for index, line in enumerate(lyrics.splitlines(), start=1):
            if len(line.split()) > words_per_line:
                add("music.line.dense", "warning",
                    f"Lyric line {index} has {len(line.split())} words; simplify for children.", 7)
                break

    if not spec.get("vocal_direction", "").strip():
        add("music.voice.unspecified", "warning",
            "Specify clear Standard German diction and audible articles.", 8)

    errors = any(f["severity"] == "error" for f in findings)
    warnings = any(f["severity"] == "warning" for f in findings)
    return {
        "module": "German Educational Music QA",
        "passed": not errors,
        "decision": "block" if errors else ("review" if warnings else "preflight_pass"),
        "risk_score": min(100, sum(f["points"] for f in findings)),
        "target_counts": counts,
        "findings": findings,
        "manual_checks": [
            "Listen to the entire rendered song: exact lyric fidelity and no invented words.",
            "Check every German word, article stress and Standard German pronunciation with a qualified listener.",
            "Verify age/CEFR suitability, actual tempo, repetition and vocal clarity.",
            "Review the generated melody and recording for originality/rights before publication.",
        ],
        "limitations": (
            "A deterministic text-only preflight; it does not hear audio, assess complete "
            "German grammar or certify actual CEFR proficiency."
        ),
    }


def compile_song_prompt(spec: dict[str, Any]) -> str:
    """Prepare an exact-lyrics generation prompt; never silently change user lyrics."""
    spec = _checked_spec(spec)
    review = review_song(spec)
    if not review["passed"]:
        raise ValueError("Music QA blocked generation; correct the reported errors first.")

    def single(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value)).strip()

    title = single(spec.get("title", "German educational song"))
    age = spec.get("age_range", [6, 9])
    targets = spec.get("target_vocabulary", [])
    lines = [
        f"TITLE: {title}",
        f"TASK: Create an ORIGINAL German educational song for ages {age[0]}-{age[1]}, CEFR {single(spec.get('cefr', 'A1'))}.",
        f"GENERATOR: {single(spec.get('provider', 'generic'))}",
        f"STYLE: {single(spec.get('style', 'playful, age-appropriate'))}",
        f"TEMPO: {single(spec.get('bpm', 'comfortable for clear pronunciation'))} BPM",
        f"VOCALS: {single(spec.get('vocal_direction', 'Clear Standard German diction.'))}",
        "TEACHING TARGETS: " + (", ".join(targets) if targets else "Verify with teacher."),
        "Perform the following lyrics exactly as written. Preserve words, articles, line order and repetitions.",
        "Do not invent extra lyrics or add spoken narration.",
        "EXACT LYRICS START",
        spec["lyrics"].strip(),
        "EXACT LYRICS END",
        "Production review: human verification of pronunciation, lyric fidelity and rights is required.",
    ]
    if spec.get("duration_seconds"):
        lines.insert(5, f"TARGET DURATION: {single(spec['duration_seconds'])} seconds (approximate; verify output).")
    return "\n".join(lines) + "\n"
