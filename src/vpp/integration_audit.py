"""Seeded cross-component known-answer regression simulation."""
from __future__ import annotations

import copy
import json
import random
from collections import Counter

from .consensus import audiovisual_review, compare_tracks, empirical_risk
from .intelligence_planning import cost_plan, model_route
from .model_evidence import rank_scene
from .subtitle_sync import audit_sync, parse_srt, repair_srt


def simulate_integration(seed=20261124, trials=1200):
    if type(trials) is not int or not 1 <= trials <= 10000:
        raise ValueError("Trials must be 1..10000.")
    rng = random.Random(seed)
    cases = ("clean", "wrong_source", "missing_repeat", "timing_spread",
             "duration_overrun", "same_family", "invalid_boundary", "scene_conflict",
             "visual_ambiguous", "budget", "router", "risk_sample")
    counts, failures = Counter(), []
    digest = "a"*64
    for i in range(trials):
        case = cases[i % len(cases)]
        counts[case] += 1
        start = rng.randint(1000, 4000)/1000
        words = [{"word": "Ein", "start": start, "end": start+.2, "score": .9},
                 {"word": "Verb", "start": start+.3, "end": start+.5, "score": .9}]
        first = {"backend": "whisperx", "family": "whisper", "model": "a",
                 "audio_sha256": digest, "words": words}
        other = {**first, "backend": "wav2vec2-ctc", "family": "wav2vec2",
                 "model": "b", "words": copy.deepcopy(words)}
        if case == "wrong_source":
            other["audio_sha256"] = "b"*64
        elif case == "missing_repeat":
            other["words"].pop()
        elif case == "timing_spread":
            for word in other["words"]:
                word["start"] += .2
                word["end"] += .2
        elif case == "duration_overrun":
            other["words"][-1]["end"] = 6.1
        elif case == "same_family":
            other.update(backend="faster-whisper", family="whisper")
        elif case == "invalid_boundary":
            other["words"][0]["start"] = None
        report = compare_tracks([first, other], digest, duration=6)
        expected_block = case in cases[1:7]
        ok = (report["decision"] == "blocked") == expected_block
        if not expected_block:
            captions = parse_srt("1\n00:00:00,100 --> 00:00:00,800\nEin Verb\nفعل\n")
            repair = audit_sync(captions, ["Ein Verb"], words, 6)
            fixed = parse_srt(repair_srt(captions, repair))
            after = audit_sync(fixed, ["Ein Verb"], words, 6)
            ok = ok and after["metrics"]["max_absolute_ms"] == 0 and fixed[0]["lines"] == captions[0]["lines"]
            if case == "scene_conflict":
                scenes = [{"id": "a", "start": 0, "end": .5, "required_phrases": ["Ein Verb"]},
                          {"id": "b", "start": .5, "end": 6}]
                ok = ok and audiovisual_review(fixed, scenes, 6)["decision"] == "needs_review"
            elif case == "visual_ambiguous":
                ok = ok and rank_scene(["a street", "an office"], [.2, .21])["signal"] == "ambiguous"
            elif case == "budget":
                price = rng.randint(1, 5000)
                plan = cost_plan([{"id": "a", "status": "visual_failed", "regenerate_cents": price}], price-1)
                ok = ok and plan["decision"] == "blocked_budget" and plan["paid_calls"] == 0
            elif case == "router":
                plan = model_route([{"id": "a", "task": "asr", "local": False,
                                     "weights_verified": True, "benchmark_comparable": True,
                                     "required_memory_mb": 1, "benchmark_loss": .01}], "asr", 10)
                ok = ok and plan["chosen"] is None and not plan["remote_fallback"]
            elif case == "risk_sample":
                n = rng.randint(1, 29)
                records = [{"id": str(k), "category": "test", "failed": True} for k in range(n)]
                ok = ok and empirical_risk(records, "test")["decision"] == "insufficient_data"
        if not ok or report["publication_approved"]:
            failures.append({"trial": i, "case": case})
    return {"seed": seed, "trials": trials, "counts": dict(counts),
            "failed_trials": len(failures), "failures": failures[:100],
            "decision": "pass_simulation" if not failures else "fail",
            "publication_approved": False,
            "basis": "seeded synthetic cross-component cases, not model accuracy"}


def _command(args):
    result = simulate_integration(args.seed, args.trials)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["failed_trials"] else 0


def register(sub):
    parser = sub.add_parser("integration-simulate", help="Seeded cross-component fault injection")
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--trials", type=int, default=1200)
    parser.set_defaults(func=_command)
