# Video Prompt Preflight (VPP)

An open-source, local-first **preflight linter + short-scene simulator + compact prompt compiler** for AI video generation.

VPP catches preventable prompt failures *before* you spend a generation credit. In v0.2 it can accept a normal free-form prompt, conservatively extract a Scene Spec, detect contradictions, estimate timing pressure, and compile a shorter generator-friendly prompt.

> VPP reduces preventable failures. It does **not** claim stochastic video generators can be made 100% artifact-free.

## Why

AI-video prompts often fail for predictable reasons:

- conflicting scene durations;
- too many visual actions packed into 10 seconds;
- on-screen text in the wrong language;
- unwanted automatic subtitles;
- exact spelling not constrained;
- German words assigned to an Arabic-only presenter;
- speech that cannot comfortably fit the scene;
- music/subtitle/audio instructions that contradict each other;
- long repetitive prompts that increase instruction collisions.

Most of these checks do not need another LLM call.

## v0.2: paste a normal prompt

```bash
vpp lint-prompt examples/ver_scene_1_prompt.txt
```

Example:

```text
PASS | risk=0/100 | simulation=comfortable
[INFO] preflight.clean: No deterministic preflight risks detected.
```

Convert prose to a Scene Spec:

```bash
vpp import-prompt examples/ver_scene_1_prompt.txt -o /tmp/scene.yml
```

Generate a compact candidate prompt:

```bash
vpp optimize examples/ver_scene_1_prompt.txt -o /tmp/optimized.txt --spec /tmp/scene.yml
```

For prompts containing real semantic conflicts, VPP produces a constrained candidate **and marks it for human review** instead of pretending an ambiguous choice is certainly correct.

## Scene Spec

The structured representation remains the most reliable authoring contract:

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

## What v0.2 checks

- positive scene duration;
- conflicting duration mentions in raw prompts;
- timeline overflow;
- action/event density;
- Arabic text when Arabic-on-screen is forbidden;
- exact screen-text whitelist violations;
- excessive screen-text items;
- dense Arabic dialogue for the requested duration;
- German speech assigned to an Arabic-only presenter;
- music contradictions;
- subtitle contradictions;
- presenter-language contradictions;
- rough prompt verbosity risk.

## Short-scene simulator

VPP estimates:

- speech words and estimated speech seconds;
- speech utilization of the scene;
- event count and event rate;
- timeline utilization;
- screen-text item count;
- overall state: `comfortable`, `tight`, or `overflow`.

It is a preflight budget model, not a video renderer.

## Browser UI

The `web/` app accepts a free-form prompt directly. It runs locally in the browser with no API key and no backend.

Features:

- free-form prompt import;
- PASS/FAIL + risk score;
- timing simulation;
- contradiction detection;
- extracted Scene Spec preview;
- compact compiled prompt;
- good and conflicting demo prompts.

Open `web/index.html` locally or publish it with the included GitHub Pages workflow.

## Install

```bash
git clone <your-repository-url>
cd video-prompt-preflight
python -m venv .venv
# Windows: .venv\\Scripts\\activate
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
      │                              │
      │                              ├── Linter ──> PASS / FAIL + Risk
      │                              ├── Simulator ──> timing pressure
      │                              ├── Safe Fixes
      │                              └── Compact Compiler
      │                                      │
      └──────────────────────────────────────> Generator Prompt
                                               │
                                               v
                                         AI Video Generator
                                               │
                                          future QA loop
                                               │
                                        Failure Corpus
                                               └──> regression rules
```

## Principles

1. **Deterministic first** — do not spend tokens to check what code can check.
2. **Conservative parsing** — never invent missing creative content.
3. **No silent certainty** — ambiguous conflict resolutions are marked for review.
4. **Generator-agnostic core** — provider quirks belong in adapters.
5. **Every failure becomes a test** — the system gets harder to break over time.
6. **Local-first UI** — basic preflight should work without accounts, GPUs or API keys.

## Roadmap

- **v0.3:** provider profiles, Promptfoo adapter, optional DSPy/local-model semantic reviewer, prompt comparison.
- **v0.4:** post-generation frame/audio QA, exact-text verification, VBench/VideoScore adapters, failure-memory dashboard.

## License

MIT — commercial use, modification and redistribution are allowed under the license terms.
