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
