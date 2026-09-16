# Changelog

## 0.3.0
- Added provider knowledge packs for Gemini/Veo and Runway.
- Added research-backed failure-pattern pack using VBench, T2V-CompBench and EvalCrafter categories.
- Added three conservative prompt candidates and deterministic candidate comparison.
- Added hard-constraint coverage scoring so shorter candidates cannot silently drop critical requirements.
- Added three-round review: correctness, failure prediction, independent gatekeeper.
- Added adversarial timing/text-motion checks.
- Added bundled real-world Failure Memory and local browser Failure Memory.
- Added `vpp triple-review --provider ...`.
- Upgraded browser UI with provider selection, Triple Verify, evidence links and review-round output.
- Fast and Triple Verify modes still require zero API calls.
- Expanded test suite to 14 tests.

## 0.2.0
- Added deterministic free-form prompt parser.
- Added raw-prompt contradiction detection for duration, music, subtitles and presenter language.
- Added short-scene timing simulator.
- Added `import-prompt`, `lint-prompt`, `optimize` and `simulate` CLI commands.
- Added review-required decisions for ambiguous source conflicts.
- Upgraded browser UI to accept normal prose prompts directly.
- Added conflict and free-form regression examples.
- Expanded test suite from 4 to 8 tests.

## 0.1.0
- Initial Scene Spec, deterministic linter, safe auto-fix, compact compiler, CLI and browser UI.
