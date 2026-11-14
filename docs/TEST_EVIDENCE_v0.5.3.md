# VPP v0.5.3 — CI test evidence and honest remaining limits

## Repeatable automation
- `pytest -q` on Python 3.10, 3.11 and 3.12 (GitHub Actions `tests`).
- `pytest -vv tests/test_release_acceptance.py` with real FFmpeg and Tesseract and the complete Python suite.
- `node --test tests/browser_smoke.cjs tests/browser_conformance.cjs` for DOM smoke and 13 golden Python-browser parity cases.
- `ruff check .` for the full configured lint rules, no unused imports or missed modernizations.
- Isolated Wheel install with three bundled failure-memory records verified.
- `npm run test:e2e` drives real Chromium against the real static browser UI and a generated local WebM.

## Test focus
- Film duration and aspect ratio; sampled OCR versus manual text acceptance.
- Negative and conflicting music/subtitle instructions.
- Preservation of absolute timeline offsets, duplicate/overlapping beats, no false camera-to-word conversion.
- Browser localStorage corruption, XSS text escaping, CSP, accessible file picker and text input.
- A real browser playing a whole local video; no false saved blooper on an inferred default.
- Clean CLI invalid-file errors, empty scene review state and explicit remote judge consent.

## Evidence links
- Python 3.10–3.12: https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/test.yml
- Local media acceptance/Ruff/Node: https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/release-acceptance.yml
- Real Chromium: https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/browser-e2e.yml
- GitHub Pages: https://github.com/muhamadmostafa2013-design/video-prompt-preflight/actions/workflows/pages.yml

## Not certified
- No real-world multi-language OCR/ASR benchmark with verified labels. An observed OCR token can be incorrect.
- No real pronunciation accuracy certification, or automatic proof of text legality for all frames.
- Browser automated media QA still needs a human to watch/listen to the whole video.
- No production review of SDK remote privacy or external AI-video API current behavior.
- Real Chromium on Linux is tested, but physical Android/iOS, macOS, Windows and accessibility assistive-technology passes remain to be run.
- Product remains **engineering beta** until user, security, multimedia quality and legal acceptance gates are independently verified.
