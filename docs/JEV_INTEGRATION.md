# Jev integration for VPP

VPP can optionally use TypeSafe AI's **Jev** as a semantic judge after the deterministic triple-review pipeline.

## Architecture

```text
Prompt
  ↓
VPP deterministic preflight
  ↓
Video Prompt Constitution
  ↓
A / B / C candidates
  ↓
Jev candidate judge
  ↓
deterministic utility ranking
  ↓
Jev semantic release gate
  ↓
RELEASE / REVIEW / BLOCK
```

Jev is never used as the prompt writer. VPP keeps prompt construction deterministic and uses Jev for typed probabilistic judgments.

## Stage 1 — candidate judge

All A/B/C candidates are evaluated in one System One request. For each candidate VPP asks:

- are all hard constraints preserved?
- does the candidate fit the selected provider?
- does meaningful ambiguity remain?
- what is the preventable-risk score?

Jev also gives an advisory best-candidate Choice. VPP does **not** blindly accept that Choice. The final ranking is computed in code from the returned probabilities plus VPP's deterministic hard-constraint coverage and existing candidate score.

A candidate that loses a required constraint is heavily penalized even if it otherwise looks fluent or concise.

## Stage 2 — semantic release gate

After candidate ranking, the winner gets a second typed gate:

- hard-constraint preservation probability
- provider-fit probability
- human-review probability
- preventable-risk score
- dominant risk category

VPP converts those values into:

- `release`
- `review`
- `block`

The thresholds live in code, so policy remains inspectable and testable.

## Native Jev

Install:

```bash
pip install 'video-prompt-preflight[jev]'
```

Set:

```bash
export TYPESAFE_API_KEY='...'
```

Run:

```bash
vpp jev-review prompt.txt --provider veo
```

Use `--model` only if your TypeSafe account requires an explicit model identifier.

## Test drive before Jev access

TypeSafe also publishes **System One Adapter**, a drop-in evaluation client backed by OpenAI-compatible or Anthropic models. It lets VPP exercise the same question/ranking pipeline before native Jev access is available.

OpenAI-compatible:

```bash
pip install 'video-prompt-preflight[adapter-openai]'
export OPENAI_API_KEY='...'
vpp jev-review prompt.txt --provider veo --engine openai --model <model-name>
```

Anthropic:

```bash
pip install 'video-prompt-preflight[adapter-anthropic]'
export ANTHROPIC_API_KEY='...'
vpp jev-review prompt.txt --provider veo --engine anthropic --model <model-name>
```

Adapter results are useful for workflow testing and comparison. They should not be mislabeled as native Jev results.

## Security

Never put a TypeSafe, OpenAI, or Anthropic API key in public GitHub Pages JavaScript. The browser site remains local-first and zero-API by default.

To expose Jev in the public web UI later, use a secure server-side proxy with:

- secrets stored server-side;
- strict request-size limits;
- origin/rate controls;
- no raw secret returned to the browser;
- explicit opt-in because prompts leave the browser in semantic-judge mode.

## Output QA

Jev is currently fed structured VPP state rather than raw video pixels/audio. The browser Output QA should first extract deterministic metadata, sampled-frame evidence and human-confirmed failures. Those structured results can then become another Jev state for a fast post-generation semantic gate.
