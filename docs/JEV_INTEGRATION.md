# Jev integration for VPP

VPP can optionally use TypeSafe AI's **Jev** as a semantic judge after the deterministic triple-review pipeline.

## Why Jev belongs in the judge layer

Jev is a System One model: it takes state plus typed questions and returns typed probabilistic decisions. It is not a text generator. VPP therefore keeps prompt generation/compilation deterministic and uses Jev only to judge release risk.

The integration asks atomic questions in parallel:

- Are hard constraints preserved?
- Is the selected prompt likely to fit the chosen provider?
- Does it still need human review?
- What is the remaining preventable-risk score?
- What is the dominant risk category?

VPP combines those answers in code into one of three outcomes:

- `release`
- `review`
- `block`

This preserves the existing **local-first / zero-API-call** mode. Jev is opt-in.

## Install

```bash
pip install 'video-prompt-preflight[jev]'
```

Set the TypeSafe credential using the SDK's normal environment variable:

```bash
export TYPESAFE_API_KEY='...'
```

Then run:

```bash
vpp jev-review prompt.txt --provider veo
```

Use `--model` only when your TypeSafe account requires an explicit model identifier.

## Security

Do **not** put a TypeSafe API key in the public GitHub Pages JavaScript. GitHub Pages is static and cannot keep a secret. The live website should call Jev only through a secure backend/proxy, or Jev should be used locally through the CLI.

## Output QA

Jev does not currently inspect raw video pixels/audio in this integration. VPP's browser Output QA first extracts deterministic facts and human-confirmed failures. Those structured facts can then be sent to Jev for fast semantic gating.
