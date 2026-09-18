# Video Prompt Preflight (VPP)

An open-source, local-first **preflight linter + knowledge engine + triple-review prompt factory** for AI video generation.

VPP catches preventable prompt failures *before* you spend a generation credit. v0.4 keeps the deterministic local core, expands the multi-provider Video Prompt Constitution and Output QA, and adds an optional Jev semantic-judge layer for probabilistic candidate ranking and release gating.

> VPP reduces preventable failures. It does **not** claim stochastic video generators can be made 100% artifact-free.

## Why

AI-video prompts often fail for predictable reasons: conflicting durations, crowded short scenes, wrong-language on-screen text, unwanted subtitles, exact-text drift, speaker/language confusion, dense speech, and contradictory audio instructions. Most of these checks do not need another LLM call.

## v0.4: local Triple Verify + optional Jev judge

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
vpp jev-review <prompt.txt> --provider veo
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

## Roadmap

- **v0.4 (current):** multi-provider constitution, A/B/C local review, Output QA, exact-text regression protection, optional Jev candidate judge + semantic gate.
- **v0.5:** secure web judge proxy, deeper post-generation audio/visual QA, Promptfoo/DSPy/local-model adapters and explicit token budgets.

## License

MIT — commercial use, modification and redistribution are allowed under the license terms.
