"""Bounded source-bound waveform from actual decoded audio, never synthetic peaks."""
from __future__ import annotations

import array
import math
import sys
from pathlib import Path

from .quality_engine import _one_stream, _probe, _run
from .song_alignment import _hash


def waveform(video, bins=1200):
    if type(bins) is not int or not 32 <= bins <= 2400:
        raise ValueError("Waveform bins must be 32..2400.")
    source = Path(video).resolve(strict=True)
    digest = _hash(source)
    info = _probe(source)
    audio = _one_stream(info, "audio")
    duration = float(info["format"]["duration"])
    start = float(audio.get("start_time", 0))
    if not math.isfinite(duration) or not 0 < duration <= 300 or abs(start) > .001:
        raise ValueError("Waveform requires a zero-start source up to five minutes.")
    rate = 8000
    raw = _run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-protocol_whitelist", "file,pipe",
                "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(rate),
                "-t", "301", "-f", "s16le", "-"], timeout=180)
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples or abs(len(samples)/rate-duration) > .15:
        raise ValueError("Decoded audio duration differs from media timeline.")
    count = min(bins, len(samples))
    peaks = []
    for i in range(count):
        values = samples[i*len(samples)//count:(i+1)*len(samples)//count]
        peaks.append(round(max(abs(min(values)), abs(max(values)))/32768, 5))
    if _hash(source) != digest:
        raise ValueError("Source changed during waveform decoding.")
    return {"video_sha256": digest, "duration_seconds": duration,
            "decoded_audio_seconds": len(samples)/rate, "sample_rate": rate,
            "peaks": peaks, "publication_approved": False,
            "limitations": "Mono peak envelope, not phoneme or timing evidence."}
