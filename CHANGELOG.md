# Changelog

## 0.5.2 — Claude independent audit remediation
- Fixed falsely detected music conflicts, global-vs-action durations, missing "seconds" timeline ranges, and absolute gaps in compiled timelines.
- Confined static-word rewrite to actual exact-text transitions; camera animation remains a camera instruction.
- Added conservative warnings for inferred duration/partially supported Arabic text and review-required CLI exit codes.
- Ensured external Jev semantic judgments cannot override blocking deterministic preflight errors.
- Packaged the original failure-memory corpus in distributable wheels (verified via isolated installation).
- Fixed corrupt browser history entries, unavailable localStorage, metadata verdict on no-text videos and manual video-wide text whitelist checklist.
- Added SAR/rotation display ratio, sampled silent-audio analysis, local protocol restrictions and OCR whitelist/Arabic evidence.
- Added audit regression tests, actual-video tests, Node VM DOM smoke tests, and acceptance + wheel CI checks.


## 0.5.1 — release hardening / independent acceptance
- Synced version across package, CLI review output and front-end label.
- Escaped untrusted values before browser DOM insertion, including locally saved mistakes and knowledge-source links.
- Restricted source evidence hrefs to HTTPS and handled malformed local history.
- Added 15-second media load/seek timeout and 512 MiB local browser input limit.
- Added a dedicated ten-gate acceptance workflow with real MP4 and local OCR test.
- Kept optional media dependencies out of generic Python 3.10–3.12 matrix.
- Added an independent Claude review prompt and honest release-evidence checklist.


## 0.5.0 — local video QA evidence
- Added offline `vpp check-video` CLI for actual video duration/aspect/audio-stream checks.
- Added optional sampled-frame OCR with locally installed Tesseract and language packs.
- Added optional speech transcription through a PRE-DOWNLOADED local faster-whisper model.
- Exportable JSON evidence; content checks always require human confirmation.
- No remote uploads, prompt logging or automatic model downloads.
- Added regression tests for missing audio, metadata mismatch, OCR uncertainty, offline model gating.
- Synchronized package, VERSION, changelog, README and roadmap version references.

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
