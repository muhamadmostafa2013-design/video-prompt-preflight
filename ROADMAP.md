# Roadmap

## Shipped
- **0.1–0.3:** Scene Spec, free-text parser, deterministic checks and local browser review.
- **0.4:** provider constitution, triple review, optional Jev judge, browser upload,
  duration/aspect checks and eight sampled frames with human exact-text confirmation.
- **0.5:** local `check-video` CLI with optional Tesseract OCR and offline ASR,
  machine-readable JSON report and explicit human approval gate.

## Not yet shipped / subject to validation
- Browser-native automatic OCR and transcript checking without external services.
- Provider API generation connectors (credentials, costs and provider approval required).
- Large-scale benchmarking against real video outputs and human annotations.
- Automated pronunciation grading, subtitle correctness and continuous video coverage.
- Secure web judge proxy and professional multi-user workspace.

## Release rule
Do not claim video correctness from sample frames or a transcript alone.
The automated status is evidence, not a certificate; content always requires human review.
