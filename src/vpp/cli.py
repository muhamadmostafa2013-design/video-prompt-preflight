from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .analyzer import analyze_scene
from .compiler import compile_scene
from .fixer import auto_fix_scene
from .german_music_qa import compile_song_prompt, review_song
from .io import dump_scene, load_scene
from .jev_judge import jev_review
from .media_qa import MediaQAError, inspect_video
from .optimizer import optimize_prompt
from .parser import parse_prompt
from .prompt_analyzer import analyze_prompt
from .simulator import simulate_scene
from .triple_review import triple_review

PROVIDERS = [
    "generic",
    "gemini_omni",
    "veo",
    "runway",
    "firefly",
    "luma",
    "kling",
    "wan",
    "pixverse",
    "minimax",
    "higgsfield",
    "pika",
    "seedance",
    "midjourney",
    "grok",
    "vidu",
    "dreamina",
    "canva",
    "sora_legacy",
]


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_lint(args: argparse.Namespace) -> int:
    scene = load_scene(args.file)
    report = analyze_scene(scene)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if report.passed else 'FAIL'} | risk={report.risk_score}/100")
        for f in report.findings:
            print(f"[{f.severity.upper()}] {f.rule_id}: {f.message}")
            if f.suggestion:
                print(f"  -> {f.suggestion}")
    return 0 if report.passed else 2


def cmd_compile(args: argparse.Namespace) -> int:
    scene = load_scene(args.file)
    report = analyze_scene(scene)
    if not report.passed and not args.force:
        print("Refusing to compile because preflight failed. Use --force to override.", file=sys.stderr)
        return 2
    print(compile_scene(scene), end="")
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    scene = load_scene(args.file)
    fixed = auto_fix_scene(scene)
    dump_scene(fixed, args.output)
    report = analyze_scene(fixed)
    print(f"Wrote {args.output} | {'PASS' if report.passed else 'FAIL'} | risk={report.risk_score}/100")
    return 0 if report.passed else 2


def cmd_import_prompt(args: argparse.Namespace) -> int:
    scene = parse_prompt(_read_text(args.file))
    dump_scene(scene, args.output)
    report = analyze_scene(scene)
    print(f"Wrote {args.output} | {'PASS' if report.passed else 'FAIL'} | risk={report.risk_score}/100")
    if not report.passed:
        return 2
    if not scene.get("parse_meta", {}).get("duration_explicit", False):
        return 3
    return 0


def cmd_lint_prompt(args: argparse.Namespace) -> int:
    scene, report = analyze_prompt(_read_text(args.file))
    payload = {"report": report.to_dict(), "simulation": simulate_scene(scene).to_dict(), "scene": scene}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if report.passed else 'FAIL'} | risk={report.risk_score}/100 | simulation={payload['simulation']['status']}")
        for f in report.findings:
            print(f"[{f.severity.upper()}] {f.rule_id}: {f.message}")
            if f.suggestion:
                print(f"  -> {f.suggestion}")
    if not report.passed:
        return 2
    if any(f.rule_id in {"prompt.duration.inferred", "prompt.arabic.limited"} for f in report.findings):
        return 3
    return 0


def cmd_optimize(args: argparse.Namespace) -> int:
    result = optimize_prompt(_read_text(args.file))
    output = result["optimized_prompt"]
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote {args.output} | before={result['before']['risk_score']}/100 | after={result['after']['risk_score']}/100 | review_required={str(result['requires_review']).lower()}")
        for decision in result["decisions"]:
            print(f"  decision: {decision}")
    else:
        print(output, end="")
    if args.spec:
        dump_scene(result["scene"], args.spec)
    if result["requires_review"]:
        print("DRAFT ONLY: unresolved source constraints require human approval.", file=sys.stderr)
        return 3
    return 0 if result["after"]["passed"] else 2


def cmd_triple_review(args: argparse.Namespace) -> int:
    result = triple_review(_read_text(args.file), provider=args.provider)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if result['passed'] else 'FAIL'} | provider={result['provider']} | score={result['heuristic_score']}/100 | confidence={result['confidence_band']}")
        for rnd in result["rounds"]:
            print(f"ROUND {rnd['round']} — {rnd['name']}")
            for f in rnd.get("findings", []):
                tier = f.get("evidence_tier")
                tier_text = f" · tier={tier}" if tier else ""
                print(f"  [{f['severity'].upper()}] {f['agent']} · {f['rule_id']}{tier_text}: {f['message']}")
            if rnd.get("winner"):
                print(f"  winner: {rnd['winner']}")
        print("\nFINAL PROMPT\n------------")
        print(result["final_prompt"])
    return 0 if result["passed"] else 2


def cmd_jev_review(args: argparse.Namespace) -> int:
    if not args.allow_remote_judge:
        print("Remote judge is opt-in. Re-run with --allow-remote-judge to send prompt text and review metadata to the selected SDK/provider.", file=sys.stderr)
        return 2
    text = _read_text(args.file)
    local = triple_review(text, provider=args.provider)
    client = None
    model = args.model

    if args.engine in {"openai", "anthropic"}:
        if not args.model:
            print("--model is required when --engine is openai or anthropic.", file=sys.stderr)
            return 2
        try:
            from system_one_adapter import SystemOneAdapterClient
        except ImportError:
            extra = "adapter-openai" if args.engine == "openai" else "adapter-anthropic"
            print(
                f"Adapter mode is optional. Install it with: pip install 'video-prompt-preflight[{extra}]'",
                file=sys.stderr,
            )
            return 2

        client = SystemOneAdapterClient(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
            n_retry_malformed_structure=1,
            provider=args.engine,
            model=args.model,
        )
        model = None

    try:
        result = jev_review(local, original_prompt=text, model=model, client=client)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()

    payload = {"triple_review": local, "judge_engine": args.engine, "jev": result}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        winner = result["candidate_judge"]["winner"]
        gate = result["semantic_gate"]["decision"]
        print(
            f"JEV {gate['decision'].upper()} | provider={args.provider} "
            f"| winner={winner['name']} | utility={winner['utility']:.3f}"
        )
        print(
            f"constraints={winner['hard_constraints_probability']:.2f} "
            f"| provider_fit={winner['provider_fit_probability']:.2f} "
            f"| ambiguity={winner['ambiguity_probability']:.2f} "
            f"| candidate_risk={winner['risk_score']:.2f}/4"
        )
        print(
            f"gate_risk={gate['risk_score']:.2f}/4 "
            f"| dominant_risk={gate['dominant_risk']} "
            f"| confidence={gate['confidence']:.2f}"
        )
        print("\nJEV CANDIDATE RANKING")
        for i, row in enumerate(result["candidate_judge"]["ranking"], start=1):
            print(
                f"  {i}. {row['name']} | utility={row['utility']:.3f} "
                f"| constraints={row['hard_constraints_probability']:.2f} "
                f"| fit={row['provider_fit_probability']:.2f} "
                f"| risk={row['risk_score']:.2f}/4"
            )
        print("\nFINAL PROMPT\n------------")
        print(result["final_prompt"])
    return 0 if result["decision"] == "release" else 2


def cmd_simulate(args: argparse.Namespace) -> int:
    scene = load_scene(args.file)
    simulation = simulate_scene(scene)
    print(json.dumps(simulation.to_dict(), ensure_ascii=False, indent=2) if args.json else (
        f"simulation={simulation.status} | speech={simulation.spoken_words} words/{simulation.estimated_speech_seconds}s "
        f"| events={simulation.event_count} | timeline={simulation.timeline_seconds}/{simulation.duration_seconds}s"
    ))
    return 0 if simulation.status != "overflow" else 2



def cmd_check_video(args: argparse.Namespace) -> int:
    try:
        scene = load_scene(args.spec) if args.spec else {}
        result = inspect_video(
            args.video, scene, ocr=args.ocr, ocr_lang=args.ocr_lang,
            asr_model=args.asr_model, frames=args.frames,
        )
        if not args.spec or not scene:
            result["checks"].append({
                "name": "missing_scene_spec", "status": "review",
                "reason": "No scene spec supplied: duration, ratio and content cannot be verified",
            })
            if result["decision"] == "pass":
                result["decision"] = "review"
    except (MediaQAError, ValueError, OSError) as exc:
        print(f"Media QA error: {exc}", file=sys.stderr)
        return 2
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(f"{result['decision'].upper()} | {result['metadata']['duration_seconds']}s "
              f"| {result['metadata']['width']}x{result['metadata']['height']}")
        for check in result["checks"]:
            print(f"[{check['status'].upper()}] {check['name']}: "
                  f"{check.get('expected', check.get('reason', ''))}")
        if args.output:
            print(f"Evidence saved: {args.output}")
    # 0 = metadata-only pass, 3 = requires human review, 2 = failed gate.
    return {"pass": 0, "review": 3, "fail": 2}[result["decision"]]




def cmd_music_qa(args: argparse.Namespace) -> int:
    spec = yaml.safe_load(_read_text(args.file))
    report = review_song(spec)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['decision'].upper()} | German Educational Music QA | risk={report['risk_score']}/100")
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['rule_id']}: {finding['message']}")
        print("OUTPUT QA: Human listening review is mandatory after generation.")
    if args.prompt_out and report["passed"]:
        Path(args.prompt_out).write_text(compile_song_prompt(spec), encoding="utf-8")
        if not args.json:
            print(f"Prompt draft written to {args.prompt_out}")
    return 2 if not report["passed"] else (3 if report["decision"] == "review" else 0)


def cmd_compile_song(args: argparse.Namespace) -> int:
    spec = yaml.safe_load(_read_text(args.file))
    report = review_song(spec)
    prompt = compile_song_prompt(spec)
    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
        print(f"Song prompt written to {args.output}")
    else:
        print(prompt, end="")
    return 3 if report["decision"] == "review" else 0


def cmd_director_review(args: argparse.Namespace) -> int:
    """Full offline production preflight without contacting Gemini."""
    from .production import _yaml, evaluate_preflight, validate_job

    root = Path(args.root).resolve()
    job = validate_job(_yaml(Path(args.file)), root)
    result = evaluate_preflight(job)
    report = result["director"]
    payload = {"director": report, "source_qa": result["qa"]}
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.prompt_out and report["ready_for_generation"]:
        Path(args.prompt_out).write_text(
            "\n\n--- NEXT SCENE ---\n\n".join(result["prompts"]) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{report['decision'].upper()} | AI Prompt Director | "
              f"{len(report['findings'])} finding(s)")
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['stage']} / "
                  f"{finding['rule_id']}: {finding['message']}")
            print(f"  -> {finding['suggestion']}")
        print("No remote checks. Generated output still requires a human review.")
    return 2 if report["decision"] == "blocked" else (
        3 if report["decision"] == "needs_revision" else 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vpp", description="Video Prompt Preflight")
    sub = p.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help="Analyze a structured Scene Spec")
    lint.add_argument("file")
    lint.add_argument("--json", action="store_true")
    lint.set_defaults(func=cmd_lint)

    compile_p = sub.add_parser("compile", help="Compile a Scene Spec into a compact prompt")
    compile_p.add_argument("file")
    compile_p.add_argument("--force", action="store_true")
    compile_p.set_defaults(func=cmd_compile)

    fix = sub.add_parser("fix", help="Apply safe deterministic fixes to a Scene Spec")
    fix.add_argument("file")
    fix.add_argument("-o", "--output", required=True)
    fix.set_defaults(func=cmd_fix)

    imp = sub.add_parser("import-prompt", help="Convert a free-form prompt into a conservative Scene Spec")
    imp.add_argument("file")
    imp.add_argument("-o", "--output", required=True)
    imp.set_defaults(func=cmd_import_prompt)

    lp = sub.add_parser("lint-prompt", help="Analyze a free-form AI-video prompt")
    lp.add_argument("file")
    lp.add_argument("--json", action="store_true")
    lp.set_defaults(func=cmd_lint_prompt)

    opt = sub.add_parser("optimize", help="Parse, safely fix and compile a compact prompt")
    opt.add_argument("file")
    opt.add_argument("-o", "--output")
    opt.add_argument("--spec", help="Optionally write extracted Scene Spec")
    opt.set_defaults(func=cmd_optimize)

    triple = sub.add_parser("triple-review", help="Run 3-round local multi-agent preflight")
    triple.add_argument("file")
    triple.add_argument("--provider", choices=PROVIDERS, default="generic")
    triple.add_argument("--json", action="store_true")
    triple.set_defaults(func=cmd_triple_review)


    jev = sub.add_parser("jev-review", help="Rank A/B/C with Jev or the official System One Adapter")
    jev.add_argument("file")
    jev.add_argument("--provider", choices=PROVIDERS, default="generic")
    jev.add_argument("--engine", choices=["jev", "openai", "anthropic"], default="jev",
                     help="Judge backend. 'jev' uses TypeSafe; openai/anthropic use TypeSafe's System One Adapter.")
    jev.add_argument("--model", help="Optional Jev model id; required for adapter engines")
    jev.add_argument("--json", action="store_true")
    jev.add_argument("--allow-remote-judge", action="store_true",
                     help="Explicitly consent to sending prompt contents to the selected judge/provider")
    jev.set_defaults(func=cmd_jev_review)

    sim = sub.add_parser("simulate", help="Estimate timing pressure for a Scene Spec")
    sim.add_argument("file")
    sim.add_argument("--json", action="store_true")
    sim.set_defaults(func=cmd_simulate)
    media = sub.add_parser("check-video", help="Local video metadata QA + optional OCR/ASR evidence")
    media.add_argument("video", help="Path to local video file")
    media.add_argument("--spec", help="Scene Spec YAML/JSON containing duration, aspect and text")
    media.add_argument("--ocr", action="store_true", help="OCR sampled frames via local Tesseract")
    media.add_argument("--ocr-lang", default="eng", help="Installed Tesseract language packs, e.g. eng+deu")
    media.add_argument("--asr-model", help="Directory of a PRE-DOWNLOADED faster-whisper model (offline only)")
    media.add_argument("--frames", type=int, choices=range(1, 41), metavar="1..40", default=8)
    media.add_argument("--json", action="store_true")
    media.add_argument("-o", "--output", help="Save full structured QA evidence as JSON")
    media.set_defaults(func=cmd_check_video)


    music = sub.add_parser("music-qa", help="German Educational Music QA (local text-only preflight)")
    music.add_argument("file", help="Structured song YAML/JSON spec")
    music.add_argument("--json", action="store_true")
    music.add_argument("--prompt-out", help="Write draft generator prompt only if no blocking findings")
    music.set_defaults(func=cmd_music_qa)

    song = sub.add_parser("compile-song", help="Compile QA-approved German song spec without changing lyrics")
    song.add_argument("file")
    song.add_argument("-o", "--output")
    song.set_defaults(func=cmd_compile_song)


    director = sub.add_parser("director-review", help="AI Prompt Director educational QA and final Gemini gate")
    director.add_argument("file", help="Production YAML/JSON job spec")
    director.add_argument("--root", default=".", help="Repository root for relative song specs")
    director.add_argument("--json", action="store_true")
    director.add_argument("-o", "--output", help="Write full JSON preflight report")
    director.add_argument("--prompt-out", help="Write final generator prompts only if ready")
    director.set_defaults(func=cmd_director_review)

    from .song_alignment import register as register_song_alignment
    register_song_alignment(sub)
    from .subtitle_sync import register as register_subtitle_sync
    register_subtitle_sync(sub)
    from .quality_engine import register as register_quality_engine
    register_quality_engine(sub)
    from .quality_evidence import register as register_quality_evidence
    register_quality_evidence(sub)
    from .model_evidence import register as register_model_evidence
    register_model_evidence(sub)
    from .intelligence_workflow import register as register_intelligence_workflow
    register_intelligence_workflow(sub)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        status = args.func(args)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as exc:
        print(f"VPP input error: {exc}", file=sys.stderr)
        status = 2
    raise SystemExit(status)


if __name__ == "__main__":
    main()
