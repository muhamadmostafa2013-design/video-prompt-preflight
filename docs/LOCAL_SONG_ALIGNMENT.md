# Local song alignment (experimental)

The new Python CLI command is a post-production companion to `music-qa`. It does not change the browser app or certify human listening. No paid API or audio upload is required. Models need local CPU/GPU compute and initial weight downloads.

## Setup (Python 3.11 recommended)

Install VPP with `pip install -e .`. Install FFmpeg/ffprobe and use separate virtual environments for Demucs and WhisperX if their PyTorch dependencies conflict: `python -m pip install demucs` and `python -m pip install whisperx` in the respective environments. Follow upstream [Demucs](https://github.com/facebookresearch/demucs) and [WhisperX](https://github.com/m-bain/whisperX) installation instructions. Models, licenses and GPU compatibility vary. These optional packages are not required by ordinary VPP commands.

```bash
vpp align-song song.mp3 --lyrics exact-sung-de.txt --translations ar.txt -o alignment-run --allow-model-downloads --demucs-python /path/to/demucs/python --whisperx-python /path/to/whisperx/python
```

Use absolute interpreter paths (on Windows: venv\\Scripts\\python.exe). For a cached/offline run omit --allow-model-downloads and provide --demucs-repo containing htdemucs weights; WhisperX and its German alignment/VAD weights must already be installed/cached. Model download consent does not authorize upload of recordings. Use a fresh output directory each time. Lyrics must include repeated sung lines and improvised words, not section labels; translations are optional and have exactly one line per nonblank German lyric line.

The command separates the vocals, checks stem duration, transcribes German and uses WhisperX phoneme alignment (not estimated beat timing). It preserves raw output and logs, rejects missing/low-confidence timestamps, reordered or omitted words, repeated-chorus mismatches and overlaps. It does not interpolate missing times. The score floor is a heuristic, not a calibrated confidence. Exact lexical match is conservative; fix the reference only after checking the recording. Output is a draft SRT only on complete matching evidence. The JSON includes original/vocal SHA-256 hashes and every unresolved issue; exit 2 means blocked, 3 means mandatory human listening review. Never auto-publish based on this result. For manual QA, play the whole song at original speed and verify every word and translation against the timestamps; inspect backing-vocal repetitions separately.

## Test evidence

The real song was probed as 180.479958 seconds, and Demucs execution was attempted. The pretrained weights could not download due to DNS failure in the execution environment; WhisperX is not installed there. No real-song word alignment or human listening claim is made. Unit tests use synthetic word evidence to exercise the release gate, not actual song inference. Real-model integration remains pending. Do not commit private source recordings or derived transcripts.


## Subtitle Sync QA and safe repair (v0.6 development)

Run a new `align-song` job first: older runs do not include the evidence schema
and hashes required by this gate. Then use:

```bash
vpp subtitle-sync old.srt --audio song.mp3 --lyrics exact-sung-de.txt \
  --alignment-run alignment-run -o sync-audit --repair
```

This is free/local, with no model inference required during the SRT audit.
It uses the saved WhisperX word intervals, not beat timing. The existing
SRT may split/merge reference lines if the complete German word sequence
matches exactly. Plain SRT only: German on the first text line, optional
Arabic translation(s) on subsequent lines. Indexes must be sequential.
Text mismatch, missing repeats, low scores, missing or overlapping acoustic
word intervals and evidence hash mismatches block repair. No edits to original
captions or recordings. Hashes detect file changes, not fabricated provenance.

The JSON includes signed onset and end error (positive = subtitle late),
MAE, p95 absolute boundary error (nearest-rank), max absolute error, early/late
counts, original overlaps and out-of-range cues. The first-minute report uses
cues whose acoustic start is below 60 seconds. Default tolerance 150 ms is a
configurable engineering target, not a validated perceptual limit.

With `--repair`, the program writes a separate SRT draft preserving all
German/Arabic text and uses actual first/last word intervals, then re-audits
the resulting draft. A zero residual means agreement with machine evidence,
not proof that speech recognition or translation is correct. Exit 3 always
means review required; exit 2 blocks. No burned-in video replacement, audio
rewriting, human approval or automatic publication. The raw ASR files and
report may include personal data; keep them local.

Regression fixtures deliberately inject unequal late and early cues,
overlaps, missing repetitions, incorrect German, corrupt timestamps and
modified source files. These validate the algorithm, not real-song accuracy.


## v0.6 quality-engine experimental milestone

- `vpp model-readiness`: inspect local binaries/packages, never switch to paid services.
- `vpp quality-simulate --seed 20261124 --trials 600`: reproducible known-answer tests with six fault types. CI runs three seeds (1,800 trials).
- `vpp caption-language-qa old.srt --glossary glossary.json`: DE/AR script and explicit lexical glossary hints, not semantic translation/grammar grading.
- `vpp visual-scan clean.mp4`: full decoder pass, one-second visual samples, dark/change/still hints. Not identity or scene matching.
- `vpp repair-video clean.mp4 --audio clean.mp4 --lyrics exact-sung-de.txt --srt old.srt --alignment-run alignment-run -o review-output --clean-source`: recompute repair from source-bound evidence, mux selectable subtitles, re-extract and compare SRT, preserve exact audio/video packet hashes and timestamps. Add `--burn` to create an experimental libass rendered draft (visual verification required; video re-encoded). Use a clean source without baked captions. Align the exact same media first; different decoded audio or timeline blocks repair.

No publication approval is generated; exit 3 = review. Actual media mux tests use a synthetic tone, not real singing. The synthetic fault corpus encodes error types without private recordings. Real acoustic benchmarks, human annotated ground truth, learned visual identity/scene matching, contextual grammar and translation assessment remain unvalidated. The new CLI is not a browser feature. `--burn` requires manual glyph/RTL/safe-area QA.


### Independent evaluation and feedback

- `vpp benchmark-alignment --audio source.mp3 --reference human.json --prediction machine.json`. Each JSON object must include `audio_sha256` and `words` (list of word/start/end records in seconds); reference additionally declares `annotation_source: "human"`. The declaration is not proof. Word edit distance/WER and, only for exact word sequences, boundary MAE/p95 and timing tolerance metrics are reported. Use independently annotated real recordings before claiming acoustic accuracy.
- `vpp scene-review --expected expected.json --observed observed.json --duration 30`. Both manifests contain scene IDs and start/end seconds; expected rows include required_tags/forbidden_tags arrays; observed rows contain tags annotated by a reviewer. Checks coverage, alignment and explicit tag differences. No image recognition is implied.
- `vpp failure-memory --file local-memory.json --record subtitle_drift`. Local aggregate categories and counts only, with regression test mapping. Omit --record to view prioritized failures. Single writer; no automatic rule/model training. Do not commit local memory or private media.

These components provide evidence infrastructure, not a trained visual/language model.
