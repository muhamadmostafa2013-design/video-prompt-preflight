# VPP v0.5.1 — Release Acceptance / Independent Review Notes

**Date:** 2026-11-14  |  **Scope:** local-first Python CLI + static browser tool

## Implemented and checked
- Package / VERSION / vpp.__version__ / triple-review version aligned as 0.5.1.
- HTML-injection escaping added in web/ui.js and legacy web/app.js; external evidence links now only accept HTTPS.
- Browser localStorage failure history rejects non-array payloads.
- Browser video processing rejects files above 512 MiB and uses a bounded media-event timeout.
- v0.5 already supports optional offline ffprobe, FFmpeg, Tesseract OCR and pre-downloaded faster-whisper local ASR via check-video CLI.
- Optional OCR and ASR results are evidence requiring human confirmation; no claim of automatic pronunciation grading.

## Ten reproducible acceptance tests
Run: `pytest -vv tests/test_release_acceptance.py` on a system with ffmpeg/ffprobe, Tesseract English, Pillow and pytesseract.
1. Version and report contract.
2. Good prompt / exact-screen-text acceptance.
3. Conflicting instructions rejected.
4. Prompt optimization preserves hard requirements.
5. Three independent review rounds run.
6. Real MP4 generated and successfully probed.
7. Wrong duration and aspect rejected.
8. Speech requested but audio missing rejected.
9. Real local OCR remains advisory and human review required.
10. Browser text escaping + refusal of remote ASR model names.

**CI evidence:** https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/release-acceptance.yml
**Python compatibility tests:** https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/test.yml
**Live page deployment:** https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/pages.yml

## Not verified / must not be sold as complete
- Browser-local OCR and ASR are not implemented in the GitHub Pages interface; they require optional local CLI tooling.
- OCR samples selected frames, and cannot certify all text throughout a video.
- ASR transcript is not a phoneme-level pronunciation check and can hallucinate.
- No externally verified multilingual, multi-provider real-video benchmark or user acceptance trial.
- No direct paid video generation connection or credentials to Veo/Runway/Kling or other APIs.
- No automatic commercial billing, multiuser team backend, legal review, app-store packaging or independent penetration test.
- Current static CI is not a substitute for real mobile browser/accessibility acceptance testing.

## Independent reviewer
Use `docs/CLAUDE_INDEPENDENT_REVIEW_PROMPT_AR.md` and read the actual repository tree. Report failures and missing test evidence without assuming a PASS from prior text.

## Installation snapshot
`pip install -e '.[dev,media-ocr]'`, then `pytest -q` and `vpp check-video your-video.mp4 --spec examples/ver_scene_1.yml --ocr --ocr-lang eng --json`.
Install ffmpeg/ffprobe/Tesseract on PATH separately. Local ASR additionally requires `media-asr` and a downloaded local model directory.

**Release classification:** tested local-first engineering beta; not independently certified commercial production.
