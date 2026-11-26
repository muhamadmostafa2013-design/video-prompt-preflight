# Roadmap

## Shipped
- **0.1–0.3:** Scene Spec, free-text parser, deterministic checks and local browser review.
- **0.4:** provider constitution, triple review, optional Jev judge, browser upload,
  duration/aspect checks and eight sampled frames with human exact-text confirmation.
- **0.5:** local `check-video` CLI with optional Tesseract OCR and offline ASR,
  machine-readable JSON report and explicit human approval gate.

- **0.5.3:** 13 shared Python/browser semantic cases, real Chromium E2E, full Ruff, whole-video playback,
  explicit remote judge consent, secure browser UI, and no false acceptance of missing metadata.

## Not yet shipped / subject to validation
- Browser-native automatic OCR and transcript checking without external services.
- Provider API generation connectors (credentials, costs and provider approval required).
- Large-scale benchmarking against real video outputs and human annotations.
- Automated pronunciation grading, subtitle correctness and continuous video coverage.
- Secure web judge proxy and professional multi-user workspace.

## Release rule
Do not claim video correctness from sample frames or a transcript alone.
The automated status is evidence, not a certificate; content always requires human review.


## v0.6 development branch — quality-engine milestones

- Local word-alignment integration and source-bound subtitle repair.
- Review-only MP4 mux/burn draft, encoded packet checks, full decode and sampled visual heuristics.
- Curated DE/AR glossary QA, local model readiness, seeded fault injection.
- Independent annotation benchmark, reviewer-supplied scene checks, aggregate failure memory.
- Still gated: real-song inference and measured accuracy, real-world benchmarks, learned identity/scene/semantic and grammar analysis, production browser integration, safe-area/RTL visual verification and human release sign-off.

## v0.7 development branch

- Multi-family consensus and bounded local repair; independent German CTC and optional local phone inference.
- Caption/scene interval review, sampled appearance-description continuity and curriculum constraints.
- Empirical failure-rate reporting, budget planning and local model routing; no automatic provider calls.
- Seeded prompt mutation regressions and a local summary dashboard.
- Remaining validation: annotated real singing, model-backed phone evaluation, real visual benchmarks, calibrated prediction and an integrated model execution interface. No automatic publication.
