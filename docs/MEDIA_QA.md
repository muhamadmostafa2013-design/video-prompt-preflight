# Offline media QA — v0.5

The browser's existing Output QA checks video metadata, samples eight frames and
asks a person to confirm on-screen text. The optional `check-video` CLI adds
**local** OCR and ASR evidence without a cloud account. Neither OCR nor speech
recognition can guarantee spelling, subtitles, accent or pronunciation.

## Install

```bash
pip install -e '.[dev,media-ocr]'
# Ubuntu/Debian:
sudo apt install ffmpeg tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu
# Windows/macOS: install ffmpeg/ffprobe and Tesseract on PATH; add desired language packs.
```

Local metadata-only mode needs **ffprobe** but no Python extras:

```bash
vpp check-video video.mp4 --spec examples/ver_scene_1.yml --json -o qa-report.json
```

Add OCR sampled at eight points (1–40 configurable):

```bash
vpp check-video video.mp4 --spec examples/ver_scene_1.yml --ocr --ocr-lang eng+deu --frames 16 --json -o qa-report.json
```

### Optional offline speech evidence

```bash
pip install -e '.[media-asr]'
vpp check-video video.mp4 --spec examples/ver_scene_1.yml \
  --asr-model /absolute/local/path/to/ctranslate2-whisper-model --json -o qa-report.json
```

**The model directory must already exist locally.** A model name such as
`small` is rejected to avoid an implicit download. No microphone access,
network API call or persistent raw audio is involved. Speech output is
transcription evidence only; the reviewer must compare it to the script by
listening. Language/accent/pronunciation quality is **not** automatically certified.

## Status and exit codes

| Decision | Exit | Meaning |
|---|---|---|
| pass | 0 | Applicable metadata checks passed; no requested content needs human review |
| review | 3 | OCR/ASR evidence or requested text/speech still requires human verification |
| fail | 2 | Video metadata/audio requirement fails, or command/dependency failed |

Never publish a video with a `review` decision without viewing and listening.
The `--json` output includes metadata, sampled-frame OCR text, exact words
observed/missed, available transcripts and explicit limitations. If OCR misses a
word it might appear between samples: the result is **review**, not a false
claim of absence. OCR can also mistake words: a detected match is not final
proof.

## Privacy and failure handling

- Input file remains on the user's computer; no upload, server, external API,
  audio recording or persistent raw-media storage.
- Temporary frame images are removed when the process exits normally.
- The program never installs model weights or downloads language packs.
- If a dependency, stream or file is unavailable the command fails closed.
- Report JSON can contain recognized personal information; treat it as sensitive
  and only share it deliberately.
- For commercial release, add signed installers, security review, accessibility,
  measured evaluation on real videos and independent human acceptance tests.

## Deliberate product boundary

VPP **reviews prompts and generated outputs**; it is not itself a video
generator. Direct Gemini/Veo/Runway generation requires separate provider
accounts, API availability/permissions and billing; it has not been enabled
without the owner's credentials and explicit deployment decision.
