# Video Prompt Preflight (VPP)

An open-source, local-first **preflight linter + knowledge engine + triple-review prompt factory** for AI video generation.

VPP catches preventable prompt failures *before* you spend a generation credit. v0.5.4 keeps the deterministic local core, expands the multi-provider Video Prompt Constitution and Output QA, and adds an optional Jev semantic-judge layer for probabilistic candidate ranking and release gating.

> VPP reduces preventable failures. It does **not** claim stochastic video generators can be made 100% artifact-free.

The CLI writes redirected output as UTF-8, including German and Arabic text.
Read captured `--json` output as UTF-8. To avoid shell-specific encoding when
saving a report on Windows, prefer the command's `--output` option when provided.

## Why

AI-video prompts often fail for predictable reasons: conflicting durations, crowded short scenes, wrong-language on-screen text, unwanted subtitles, exact-text drift, speaker/language confusion, dense speech, and contradictory audio instructions. Most of these checks do not need another LLM call.

## v0.5.4: local Triple Verify + optional Jev judge and media QA

```bash
vpp lint-prompt examples/ver_scene_1_prompt.txt
vpp triple-review examples/ver_scene_1_prompt.txt --provider veo
```

Triple Verify uses three local rounds:

1. **Correctness + candidate comparison** — deterministic checks and A/B/C candidate scoring.
2. **Failure prediction + evidence + memory** — provider guidance, research taxonomies, red-team checks and prior failures.
3. **Independent gatekeeper** — blocks hard errors, timing overflow and any candidate that drops required constraints.

The browser UI keeps the local zero-API flow. Jev is opt-in through the CLI or a future secure backend; see `docs/JEV_INTEGRATION.md`.

## Scene Spec

```yaml
name: ver- hook
duration_seconds: 10
spoken:
  arabic: "..."
screen_text: ["ver-", "laufen", "sich verlaufen"]
text_whitelist: ["ver-", "laufen", "sich verlaufen"]
rules:
  no_arabic_on_screen: true
  no_auto_subtitles: true
  no_background_music: true
  presenter_arabic_only: true
```

Then:

```bash
vpp lint examples/ver_scene_1.yml
vpp simulate examples/ver_scene_1.yml
vpp compile examples/ver_scene_1.yml
```

## Deterministic core checks

- positive scene duration and duration conflicts;
- timeline overflow and event density;
- Arabic text when Arabic-on-screen is forbidden;
- exact screen-text whitelist violations;
- dense dialogue for the requested duration;
- German speech assigned to an Arabic-only presenter;
- music, subtitle and presenter-language contradictions.

## Knowledge Engine

Current lightweight packs:

- **Gemini/Veo:** shot structure, explicit audio ownership and ordered play-by-play for complex action, grounded in Google DeepMind's Veo prompt guide.
- **Runway:** positive phrasing, motion focus and duration-vs-motion guidance, grounded in official Runway guides.
- **Research:** temporal consistency, compositional complexity and separated QA dimensions, mapped to VBench, T2V-CompBench and EvalCrafter taxonomies.

These are advisory unless a failure pattern is promoted into a deterministic regression rule.

## Browser UI

The `web/` app runs locally in the browser with no API key and no backend.

Features:

- provider selector for Generic, Gemini/Veo and Runway;
- Fast Analyze mode with zero API calls;
- Triple Verify with three local review rounds and zero API calls;
- evidence links for knowledge-backed findings;
- three prompt candidates with hard-constraint coverage scoring;
- local browser Failure Memory;
- timing simulation, contradiction detection and Scene Spec preview.

## Install

```bash
git clone https://github.com/muhamadmostafa2013-design/video-prompt-preflight.git
cd video-prompt-preflight
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

## CLI

```text
vpp lint <scene.yml>
vpp compile <scene.yml>
vpp fix <scene.yml> -o fixed.yml
vpp simulate <scene.yml>
vpp import-prompt <prompt.txt> -o scene.yml
vpp lint-prompt <prompt.txt>
vpp optimize <prompt.txt> -o optimized.txt --spec scene.yml
vpp triple-review <prompt.txt> --provider veo
vpp jev-review <prompt.txt> --provider veo --allow-remote-judge
vpp check-video <video.mp4> --spec <scene.yml> [--ocr] [--asr-model /local/model]
```

## Regression-first workflow

```text
real generator failure
        ↓
minimal reproduction prompt/spec
        ↓
new deterministic rule where possible
        ↓
regression test
        ↓
future prompts blocked before generation
```

The first regression corpus comes from a multilingual Arabic/German educational-video workflow where generated text and pronunciation constraints repeatedly caused wasted generations.

## Architecture

```text
Free-form Prompt
      │
      ├── Deterministic Parser ──> Scene Spec
      │                              ├── Linter
      │                              ├── Simulator
      │                              └── Compact Compiler
      ├── Candidate Factory ──> A / B / C
      ├── Knowledge Scout ──> provider + benchmark patterns
      ├── Adversarial Critic + Failure Memory
      └── Independent Gatekeeper ──> selected generator prompt
                                              │
                                              v
                                        AI Video Generator
                                              │
                                         future QA loop
                                              │
                                       Failure Corpus
```

## Principles

1. **Deterministic first** — do not spend tokens to check what code can check.
2. **Conservative parsing** — never invent missing creative content.
3. **No silent certainty** — ambiguous conflict resolutions are marked for review.
4. **Generator-agnostic core** — provider quirks belong in adapters.
5. **Every failure becomes a test** — the system gets harder to break over time.
6. **Local-first UI** — basic preflight should work without accounts, GPUs or API keys.

## Local output inspection (v0.5 CLI)

The browser already checks video duration and aspect ratio and shows eight frame samples for manual exact-text review. The new optional **offline CLI** adds sampled-frame OCR and local speech transcription evidence. Review of words, subtitles, pronunciation and timing is still required by a human.

```bash
pip install -e '.[dev,media-ocr]'
# install ffmpeg, ffprobe, Tesseract + desired language data locally
vpp check-video my-video.mp4 --spec examples/ver_scene_1.yml --ocr --ocr-lang eng+deu --json -o qa.json
```

Optional local-only ASR needs the `media-asr` extra and a pre-downloaded local faster-whisper model directory. No cloud API or implicit model download. See [Media QA guide](docs/MEDIA_QA.md).

## Roadmap

- **v0.5.4 (current):** multi-provider preflight, three local review rounds, browser metadata/frames and opt-in local OCR/ASR evidence CLI.
- **Next:** independent real-video benchmarks, accessible manual QA workflow, secure optional judge proxy, provider adapters and cost budgets.
- Generation APIs are deliberately not bundled: generator account credentials, per-video billing and explicit deployment permissions are needed.


## License

MIT — commercial use, modification and redistribution are allowed under the license terms.

## Release acceptance and independent audit

The ten explicit release gates include an actual encoded MP4 probe and locally executed OCR; see [test protocol](docs/RELEASE_ACCEPTANCE_10_GATES.md) and [Claude review handoff](docs/CLAUDE_INDEPENDENT_REVIEW_PROMPT_AR.md). This is a tested **local-first beta**, not an externally certified, error-free commercial video QA service. The static browser remains manual for text inspection; OCR/ASR are opt-in local CLI features.

## Claude independent audit remediation — v0.5.2

The 2026-11 independent review found real flaws not covered by the original
ten acceptance gates. This release adds reproductions and fixes for duration
parsing, absolute timeline intervals, constrained text transitions, negated
music language, Arabic-only prompt caveats, deterministic Jev blocking, memory
packaging, robust browser history, video verdict clarity, whitelist reviews,
SAR/rotation, sampled silent audio and local-protocol media parsing.
See [audit remediation](docs/CLAUDE_AUDIT_REMEDIATION_AR.md).

**Honest limits:** sampled OCR/ASR are probabilistic evidence, not verified
pronunciation or subtitle compliance. Browser QA asks for manual whole-video
whitelist review. Local CLI OCR/ASR require optional tooling, and real provider
APIs + multilingual real-world benchmarks remain outside this release.

## v0.5.3 deep validation, shared engine parity, and privacy

- Python and browser engines run against the SAME golden fixture corpus (13 cases covering duration, negations, timeline and text intent).
- Full Ruff lint, Python 3.10–3.12 regression suite, real FFmpeg/Tesseract + isolated Wheel installation, Node VM, and real Chromium browser tests are CI gates.
- The browser now includes a playable local video alongside sampled frames, rather than pretending eight screenshots prove video-wide compliance.
- Inferred metadata values **never** trigger automatic timing/aspect bug reports; missing specifications demand human confirmation.
- Browser CSP and keyboard-accessible form controls hardened; inline event handlers removed.
- `jev-review` explicitly requires `--allow-remote-judge` because selecting Jev/OpenAI/Anthropic can share the source prompt with a third-party SDK. Don't use it for sensitive prompts without authorization.
- Python CLI handles invalid input/YAML without raw tracebacks, and review-required inputs return status `3`.

See [deep validation and residual risks](docs/TEST_EVIDENCE_v0.5.3.md). Passing tests does **not** certify real-world multilingual OCR/ASR accuracy or any provider API.


## v0.5.4 intensive QA hardening
- All three Python and browser candidate prompts preserve absolute timeline gaps, with the actual time ranges counted as hard requirements.
- Structured Scene Spec lint now rejects invalid/nonfinite durations, malformed rules, timelines and text whitelists without crashes or changing the input.
- Local knowledge pack access validates provider file names and refuses traversal paths.
- Jev's scoring and release gate fail closed for NaN/infinite/malformed probabilities, and no candidate missing hard constraints can be promoted to RELEASE.
- Offline QA regression suite covers provider packs, randomized Arabic/German/English prompts, CLI, real video/audio, media protocol safety and mocked external judges.
- Extended Node core/triple review tests and mobile Chromium E2E checks are required in CI.

**Scope:** local-first engineering beta. Real-world accuracy of multilingual OCR/ASR and paid provider SDK/API behavior are not certified by these tests.


## German Educational Music QA (educational songs)

VPP now offers a separate **German Educational Music QA** mode for checking
German teaching-song specifications *before* generating audio. It is a local
deterministic text preflight and does **not** listen to the generated music.

- Browser: open the Director's Room page and use **German Educational Music QA**
  to check exact lyrics, articles from a limited curated dictionary, required
  vocabulary, repetitions, tempo, and vocal-instruction consistency.
- CLI: `vpp music-qa examples/german_animals_song.yml --json`
- Prompt draft: `vpp compile-song examples/german_animals_song.yml -o song-prompt.txt`
- Full setup, limitations, review checklist: [German Educational Music QA guide](docs/GERMAN_EDUCATIONAL_MUSIC_QA.md).

A passing preflight **never** proves audio pronunciation, German grammar,
educational appropriateness or music originality; inspect the finished song.


## Gemini Production Engine (manual activation, free local QA)

For educational German videos and learning songs, VPP now supports a
**spend-gated pipeline**: Triple Verify / German Educational Music QA,
Gemini Omni 1.2 Flash or Lyria 3.5, and FFmpeg MP4 assembly.

The default is **dry-run** and makes no API calls. For a realistic FFmpeg
montage test with fake input clips, run:

```bash
python -m vpp.production --spec examples/production_university_video.yml --mode demo
```

For exact options, key safety instructions, paid approval and limits see
[Gemini Production Engine guide](docs/GEMINI_PRODUCTION_ENGINE.md).

## AI Prompt Director (final German educational preflight)

The new **AI Prompt Director** verifies that a video/song production job has
an explicit learning goal, CEFR/age profile, target phrases, correct declared
German speech, a stable cast for multi-scene stories, and existing VPP/German
Music QA approval **before any paid Gemini call**.

Run the local review at zero API cost:

```bash
vpp director-review examples/production_university_video.yml --json
vpp director-review examples/production_animals_song.yml --json
vpp director-review examples/production_university_video.yml --prompt-out ready-prompt.txt
```

Decisions: **ready_for_generation**, **needs_revision**, or **blocked**.
Only a ready result can release the final prompt or enter production.
There is also a browser-only single-scene review panel in Director's Room.

A successful deterministic preflight **does not certify** German
pronunciation, full grammar, learning outcomes or the rendered video.
See [AI Prompt Director guide](docs/AI_PROMPT_DIRECTOR.md).


## Experimental v0.7 quality workflow (development branch)

See [V0.7 intelligence workflow](docs/V07_INTELLIGENCE.md) and [example project manifest](examples/quality_project.json). Use `vpp quality-run project.json -o review-run` after installing local models and completing a source-bound alignment. Multi-family consensus, guarded repair, local semantic/appearance evidence and project dashboard remain review-only. No private media upload or paid calls. Version metadata stays 0.5.4 until an accepted release; do not infer production readiness from this branch.
