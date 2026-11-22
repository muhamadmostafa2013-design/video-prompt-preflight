# Gemini Production Engine for VPP

This runner links **VPP Triple Verify → Gemini Omni 1.2 Flash or Lyria 3.5 →
FFmpeg normalization/assembly → MP4**. It can run with NO API calls using
dry-run and synthetic demo modes. The scripts are not a ChatGPT Plugin;
they run in Python locally or in a separately configured GitHub Actions job.

## Important safety and cost limits

- The default is `dry-run`: no Gemini network request, no spend.
- `demo` creates test-pattern video / sine-tone audio using free FFmpeg.
- `paid` sends ONE generation request per scene (maximum 6 scenes / 90
  seconds), or ONE song request. There is no automatic regeneration.
- `paid` requires BOTH an explicit `--mode paid` AND
  `VPP_ALLOW_PAID_GENERATION=YES`, plus a `GEMINI_API_KEY` environment secret.
- The `--max-estimated-usd` gate uses conservative **estimates**, not a
  provider-side hard spending cap. Actual charges can differ (including failed
  requests); set Google Cloud billing alerts/quotas as a separate safety layer.
- Every video scene is checked using the existing VPP Triple Verify engine.
  Every song is checked by German Educational Music QA.
- No automatic posting/publishing. Inspect every produced MP4, exact German
  pronunciation, song lyrics, visual consistency, captions and audio.
- Generated assets and prompts may be sensitive. Use a PRIVATE repository or
  private runner if footage or educational content must remain confidential.
  Artifacts from public repos may be accessible depending on repository settings.

## Python setup

```bash
python -m pip install -e .
# For paid generation only:
python -m pip install 'google-genai>=1.0'
# Install ffmpeg and ffprobe using your operating system package manager.
```

## Offline preflight (no API key)

```bash
python -m vpp.production --spec examples/production_university_video.yml
python -m vpp.production --spec examples/production_animals_song.yml --out /tmp/vpp-song
```

Reports: `production_output/preflight.json` and `prompts.txt`.

## Free full-pipeline demo with actual MP4

```bash
python -m vpp.production --spec examples/production_university_video.yml --mode demo
```

The output `production_output/final.mp4` is a SYNTHETIC test-pattern edit,
not Gemini-generated footage. It verifies FFmpeg montage and output structure.

## Paid generation (only after consent)

First save your key as `GEMINI_API_KEY` in your hosting environment or
GitHub Actions repository secrets. Never paste the key into ChatGPT, commit
it, or print it into logs.

```bash
export GEMINI_API_KEY='set-this-privately-outside-source-control'
export VPP_ALLOW_PAID_GENERATION=YES
python -m vpp.production --spec examples/production_animals_song.yml \
  --mode paid --max-estimated-usd 1.00
```

The command above is documentation ONLY. Do not copy an actual key into
shell history in shared environments; prefer a secure secret manager.

The model IDs are hard-coded to `gemini-omni-1.2-flash` (video, 720p) and
`lyria-3.5` (music). The program does not support Vertex AI credentials in
this first adapter. Google AI Studio API keys are the supported input.

## API and pricing references

- https://ai.google.dev/gemini-api/docs/omni
- https://ai.google.dev/gemini-api/docs/music-generation
- https://ai.google.dev/gemini-api/docs/pricing

As verified on 2026-11-22: Omni 1.2 Flash 720p is about USD 0.07/second of
generated output; Lyria 3.5 is about USD 0.08/song. The runner's preflight
estimate is rounded upward for basic budgeting, not a guarantee.

## Known limitations

- Educational video clips may contain misspoken words despite a clean prompt.
- The render normalizes to 720x1280 portrait or 1280x720 landscape at 30 fps,
  merges scenes and retains available audio; it does not automatically create
  trustworthy Arabic subtitles or lip-sync corrections.
- Music renders over a solid background; lyrics/subtitle timing is NOT
  auto-determined. Use Descript or a teacher to confirm timing and quality.
- The file quality check inspects playable streams, not educational quality.
- Extra post-production (burning teacher-approved SRT, logo/branding, advanced
  speech QA, direct uploads to Descript/Drive) remains a follow-on enhancement.
