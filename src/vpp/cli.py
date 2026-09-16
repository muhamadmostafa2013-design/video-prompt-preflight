from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import analyze_scene
from .compiler import compile_scene
from .fixer import auto_fix_scene
from .io import dump_scene, load_scene
from .optimizer import optimize_prompt
from .parser import parse_prompt
from .prompt_analyzer import analyze_prompt
from .simulator import simulate_scene


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
    return 0


def cmd_lint_prompt(args: argparse.Namespace) -> int:
    scene, report = analyze_prompt(_read_text(args.file))
    payload = {
        "report": report.to_dict(),
        "simulation": simulate_scene(scene).to_dict(),
        "scene": scene,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if report.passed else 'FAIL'} | risk={report.risk_score}/100 | simulation={payload['simulation']['status']}")
        for f in report.findings:
            print(f"[{f.severity.upper()}] {f.rule_id}: {f.message}")
            if f.suggestion:
                print(f"  -> {f.suggestion}")
    return 0 if report.passed else 2


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
    return 0 if result["after"]["passed"] else 2


def cmd_simulate(args: argparse.Namespace) -> int:
    scene = load_scene(args.file)
    simulation = simulate_scene(scene)
    print(json.dumps(simulation.to_dict(), ensure_ascii=False, indent=2) if args.json else (
        f"simulation={simulation.status} | speech={simulation.spoken_words} words/{simulation.estimated_speech_seconds}s "
        f"| events={simulation.event_count} | timeline={simulation.timeline_seconds}/{simulation.duration_seconds}s"
    ))
    return 0 if simulation.status != "overflow" else 2


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

    sim = sub.add_parser("simulate", help="Estimate timing pressure for a Scene Spec")
    sim.add_argument("file")
    sim.add_argument("--json", action="store_true")
    sim.set_defaults(func=cmd_simulate)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
