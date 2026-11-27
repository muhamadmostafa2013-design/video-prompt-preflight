"""Local review dashboard and multi-evidence subtitle repair gate."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .consensus import (
    audiovisual_review,
    compare_tracks,
    empirical_risk,
    phoneme_review,
)
from .intelligence_planning import (
    cost_plan,
    education_review,
    model_route,
    mutate_prompts,
)
from .quality_evidence import _read_json
from .song_alignment import _hash
from .subtitle_sync import audit_sync, load_evidence, parse_srt, repair_srt


def guarded_repair(audio, lyrics, srt, alignment_run, independent_tracks, output, tolerance_ms=100):
    """One bounded repair/recheck. Require agreement; keep the existing validated primary."""
    source_hash = _hash(Path(audio))
    words, duration, score = load_evidence(audio, lyrics, alignment_run)
    # WhisperX shares the Whisper family with faster-whisper. A truly different
    # model family is required by the agreement gate; no fake independence.
    primary = {"backend": "whisperx", "family": "whisper", "model": "alignment",
               "audio_sha256": source_hash, "words": words}
    agreement = compare_tracks([primary, *independent_tracks], source_hash, tolerance_ms, duration=duration)
    captions = parse_srt(Path(srt).read_text(encoding="utf-8-sig"))
    lines = [x.strip() for x in Path(lyrics).read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    before = audit_sync(captions, lines, words, duration, min_score=max(.5, score),
                        tolerance_ms=tolerance_ms)
    result = {"decision": "blocked", "agreement": agreement, "before": before,
              "audio_sha256": source_hash, "srt_sha256": _hash(Path(srt)),
              "duration_seconds": duration,
              "repair_attempts": 0, "publication_approved": False,
              "human_listening_verified": False}
    draft = None
    if agreement["decision"] == "review_agreement" and before["decision"] == "review":
        result["repair_attempts"] = 1
        draft = repair_srt(captions, before)
        repaired = parse_srt(draft)
        after = audit_sync(repaired, lines, words, duration, min_score=max(.5, score),
                           tolerance_ms=tolerance_ms)
        result["after"] = after
        if (after["timing_status"] != "within_tolerance" or
                after["metrics"]["max_absolute_ms"] != 0 or
                [c["lines"] for c in captions] != [c["lines"] for c in repaired]):
            draft = None
        else:
            result["decision"] = "review"
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "quality-report.json").write_text(json.dumps(result, ensure_ascii=False,
        indent=2, allow_nan=False), encoding="utf-8")
    if draft is not None:
        (destination / "REVIEW_ONLY.srt").write_text(draft, encoding="utf-8")
    write_dashboard(result, destination / "dashboard.html")
    return result


def write_dashboard(report, path):
    """Offline self-contained report viewer: escape every untrusted value, no JS or external assets."""
    if not isinstance(report, dict):
        raise TypeError("Report must be an object.")
    def safe(value):
        return html.escape(str(value))

    def section(label, value):
        raw = safe(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return f"<details><summary>{safe(label)}</summary><pre>{raw}</pre></details>"

    decision = safe(report.get("decision", "unknown"))
    def obj(value):
        return value if isinstance(value, dict) else {}

    agreement = obj(report.get("agreement"))
    before = obj(report.get("before"))
    after = obj(report.get("after"))
    cards = [("Decision", decision),
             ("Model agreement", safe(agreement.get("decision", "not supplied"))),
             ("Before: max drift (ms)", safe(obj(before.get("metrics")).get("max_absolute_ms", "—"))),
             ("After: max drift (ms)", safe(obj(after.get("metrics")).get("max_absolute_ms", "—")))]
    card_html = "".join(f"<article><small>{label}</small><b>{value}</b></article>" for label, value in cards)
    sections = "".join(section(key, value) for key, value in report.items())
    drift_sections = []
    for key, stage in obj(report.get("stages")).items():
        if not key.startswith("acoustic_drift_") or obj(stage).get("status") != "completed":
            continue
        evidence = obj(stage.get("evidence"))
        summary = obj(evidence.get("cue_drift_summary"))
        rows = evidence.get("cue_drift")
        if not isinstance(rows, list) or not summary:
            continue
        label = " / ".join(str(evidence.get(k) or "not declared") for k in ("backend", "model"))
        metrics = " · ".join(f"{name}: {safe(summary.get(field, 'not supplied'))}" for name, field in (
            ("Measured", "measured_cues"), ("Unmeasured", "unmeasured_cues"),
            ("Drift candidates", "drift_candidates"), ("Max absolute (ms)", "boundary_max_ms")))
        body = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            values = [row.get(field) for field in ("cue", "text", "screen_start_ms", "screen_end_ms",
                      "acoustic_start_ms", "acoustic_end_ms", "onset_error_ms", "offset_error_ms", "status")]
            body.append("<tr>" + "".join(f"<td>{safe(value if value is not None else '—')}</td>"
                                         for value in values) + "</tr>")
        headers = ("Cue", "German text", "Screen start", "Screen end", "Audio start", "Audio end",
                   "Onset error", "End error", "Status")
        head = "".join(f'<th scope="col">{safe(value)}</th>' for value in headers)
        drift_sections.append(f'<details open><summary>{safe(key)} · {safe(label)}</summary>'
                              f'<p>{metrics}</p><p>Milliseconds; positive error = caption late. '
                              'A dash means no measurement, not zero.</p>'
                              '<div class="scroll" tabindex="0" role="region" aria-label="Caption drift table">'
                              f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody>'
                              '</table></div></details>')
    drift_html = ('<h2>Acoustic caption review</h2>' + "".join(drift_sections)) if drift_sections else ""
    doc = ('<!doctype html><html lang="en"><meta charset="utf-8">'
           '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>VPP local quality report</title><style>*{box-sizing:border-box}'
           'body{font:16px system-ui;max-width:1120px;margin:32px auto;padding:0 18px;'
           'color:#172033;background:#f5f7fb}header{margin-bottom:20px}h1{font-size:28px;margin:0}'
           '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}'
           'article,details{background:white;border:1px solid #ccd3df;border-radius:12px;padding:16px}'
           'article small,article b{display:block}article b{margin-top:8px;font-size:22px;overflow-wrap:anywhere}'
           'details{margin:10px 0}summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}'
           'pre{white-space:pre-wrap;overflow-wrap:anywhere}.scroll{overflow-x:auto}'
           'table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccd3df;'
           'padding:8px;text-align:left;vertical-align:top}th{background:#eef2f7}'
           'footer{font-size:14px;color:#536075}</style>'
           '<main><header><h1>VPP Quality Report</h1><p>Evidence only. Human review required.</p></header>'
           f'<section class="grid" aria-label="Quality summary">{card_html}</section>'
           f'{drift_html}<h2>Evidence details</h2>{sections}'
           '<footer>Local report · No uploads · Not a publication certificate</footer></main></html>')
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(doc)


def _emit(result):
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


def _consensus(args):
    result = compare_tracks([_read_json(p) for p in args.tracks], _hash(Path(args.audio)), args.tolerance_ms)
    _emit(result)
    return 3 if result["decision"] == "review_agreement" else 2


def _heal(args):
    result = guarded_repair(args.audio, args.lyrics, args.srt, args.alignment_run,
                            [_read_json(p) for p in args.tracks], args.output, args.tolerance_ms)
    _emit(result)
    return 3 if result["decision"] == "review" else 2


def _plan(args):
    payload = _read_json(args.file)
    runners = {
        "cost-plan": lambda: cost_plan(payload["scenes"], payload["budget_cents"]),
        "model-route": lambda: model_route(payload["candidates"], payload["task"], payload["memory_mb"]),
        "education-qa": lambda: education_review(payload),
        "phoneme-review": lambda: phoneme_review(payload["reference"], payload["observed"]),
        "risk-report": lambda: empirical_risk(payload["records"], payload["category"]),
        "av-review": lambda: audiovisual_review(parse_srt(Path(payload["srt"]).read_text(encoding="utf-8-sig")),
                                               payload["scenes"], payload["duration"]),
    }
    _emit(runners[args.command]())
    return 3


def _mutate(args):
    report = mutate_prompts(args.seed, args.trials)
    _emit(report)
    return 2 if report["failed_trials"] else 0


def _dashboard(args):
    write_dashboard(_read_json(args.report), args.output)
    return 3


def register(sub):
    con = sub.add_parser("consensus", help="Compare source-bound independent model word evidence")
    con.add_argument("--audio", required=True)
    con.add_argument("--tracks", nargs="+", required=True)
    con.add_argument("--tolerance-ms", type=int, default=100)
    con.set_defaults(func=_consensus)
    heal = sub.add_parser("guarded-repair", help="One consensus-gated SRT repair and recheck")
    for name in ("audio", "lyrics", "srt", "alignment-run", "output"):
        heal.add_argument("--"+name, required=True)
    heal.add_argument("--tracks", nargs="+", required=True)
    heal.add_argument("--tolerance-ms", type=int, default=100)
    heal.set_defaults(func=_heal)
    for name in ("cost-plan", "model-route", "education-qa", "phoneme-review", "risk-report", "av-review"):
        parser = sub.add_parser(name, help="Local review-only evidence or planning")
        parser.add_argument("file", help="JSON input (explicit local paths only)")
        parser.set_defaults(func=_plan)
    mutation = sub.add_parser("prompt-mutate", help="Seeded known-answer prompt fault simulation")
    mutation.add_argument("--seed", type=int, default=20261124)
    mutation.add_argument("--trials", type=int, default=600)
    mutation.set_defaults(func=_mutate)
    dashboard = sub.add_parser("quality-dashboard", help="Create standalone escaped HTML report")
    dashboard.add_argument("report")
    dashboard.add_argument("-o", "--output", required=True)
    dashboard.set_defaults(func=_dashboard)
