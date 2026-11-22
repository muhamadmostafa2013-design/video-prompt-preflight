# German Educational Music QA

The **German Educational Music QA** module is a deterministic, local-first
preflight for German teaching-song prompts (children / adult learners). It
**does not generate or listen to songs**. It never claims to certify German
pronunciation, grammar, melody originality, CEFR compliance or commercial rights.

## Start with the sample

```bash
pip install -e '.[dev]'
vpp music-qa examples/german_animals_song.yml
vpp music-qa examples/german_animals_song.yml --json
vpp music-qa examples/german_animals_song.yml --prompt-out /tmp/animals-prompt.txt
vpp compile-song examples/german_animals_song.yml -o /tmp/animals-prompt.txt
pytest -q tests/test_german_music_qa.py
```

Exit codes: **0** = no detected blocking/advisory preflight issues;
**2** = blocked/invalid; **3** = advisory items need teacher review.
Exit code 0 means *text preflight passed*, **not** that generated audio is correct.

## Song YAML fields

- `lyrics`: exact UTF-8 lyrics, **never rewritten** by the compiler.
- `target_vocabulary`: exact German phrases that must appear.
- `min_repetitions`: minimum occurrences per phrase (default 2; low counts warn).
- `language`: `de` for strict German-script policy (default).
- `allow_bilingual`: set `true` to permit Arabic lyric text intentionally.
- `cefr`, `age_range`, `bpm`, `duration_seconds`: teaching and production profile.
- `style`, `vocal_direction`, `provider`, `title`: generator directions.
- `instrumental_only`: incompatible with written sung lyrics (blocking).
- `max_words_per_line`: warning threshold for young learners (default 12).

## Deterministic checks

- Required words/phrases absent or repeated too few times.
- A **limited, explicitly curated** set of known German noun/article pairs
  (e.g., `der Hund`, `die Katze`, `das Pferd`). This is **not** a German grammar engine.
- Arabic script in German-only lyrics.
- Vocals vs. instrumental-only contradictions.
- Unsupported CEFR label, extreme/unspecified tempo, overlong lines and
  missing vocal directions.

The browser Music QA panel provides corresponding basic checks for quick use.
For authoritative/automated reviews, use the Python CLI report. The full
song must be reviewed **after generation** by a qualified German speaker.

## Recommended teacher QA after generation

1. Listen to the whole track and compare each word against the exact lyrics.
2. Check German articles, syllable clarity, pronunciation and intelligibility.
3. Confirm actual tempo, child/CEFR fit, repetition and volume balance.
4. Check rights and originality before publishing; the prompt alone cannot establish them.

The module runs offline, no LLMs or external audio service are called.
