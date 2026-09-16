# Architecture

VPP is intentionally local-first and layered.

## 1. Free-form parser

`parser.py` conservatively extracts duration, aspect ratio, Arabic dialogue, exact screen-text blocks, timeline ranges and explicit constraints from normal prose prompts.

The parser prefers missing data over invented data.

## 2. Scene Spec

The Scene Spec is the stable intermediate representation. YAML/JSON specs are easier to lint, diff, test and compile than long prose prompts.

## 3. Deterministic preflight

`analyzer.py` checks the structured scene. `prompt_analyzer.py` checks raw-prompt contradictions that may disappear after parsing.

Examples:

- conflicting durations;
- music/subtitle conflicts;
- presenter-language conflicts;
- screen-text language policy;
- whitelist violations;
- event overload;
- speech density.

## 4. Short-scene simulator

`simulator.py` estimates speech utilization, event rate and timeline pressure. It does not attempt to render or predict visual quality.

## 5. Safe fixes and optimization

`fixer.py` applies only deterministic low-risk fixes.

`optimizer.py` creates a constrained candidate and explicitly returns `requires_review=true` when the source prompt contained semantic conflicts. This prevents the optimizer from presenting an ambiguous resolution as certain.

## 6. Compact compiler

`compiler.py` emits a short generator-facing prompt with exact text whitelists and strict constraints.

## 7. Optional intelligence (future)

LLM/vision/audio integrations remain optional adapters:

- semantic review;
- Promptfoo evaluation;
- DSPy optimization;
- local LLM review;
- post-generation frame/text/audio QA;
- VBench/VideoScore metrics.

The deterministic core must remain useful with no API key, no cloud service and no GPU.

## Failure memory

Every reproducible generator failure should become:

`failure sample -> minimal reproduction -> regression test -> deterministic rule when feasible -> permanent protection`
