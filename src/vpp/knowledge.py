from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import yaml

from .features import extract_features

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge_packs"


@dataclass
class EvidenceFinding:
    rule_id: str
    agent: str
    severity: str
    message: str
    recommendation: str
    points: int
    sources: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_pack(name: str) -> dict:
    path = KNOWLEDGE_DIR / f"{name}.yml"
    if not path.exists():
        return {"provider": name, "name": name, "rules": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _triggered(trigger: str, f: dict) -> bool:
    if trigger == "always_info":
        return True
    if trigger == "negative_instruction_overload":
        return f["negatives"] >= 4
    if trigger == "action_density_high":
        return f["actions"] > max(5, round(f["duration"] / 10 * 7))
    if trigger == "short_duration_complex_motion":
        return f["duration"] <= 5 and f["actions"] >= 4
    if trigger == "mixed_language_audio":
        return f["arabic_audio"] and f["german_screen"] and not f["presenter_arabic_only"]
    if trigger == "complex_action_without_timeline":
        return f["actions"] >= 6 and f["timeline_count"] < 2
    if trigger == "veo_sparse_structure":
        return f["has_action"] and not f["has_camera"]
    if trigger == "temporal_consistency_risk":
        return f["simulation_status"] in {"tight", "overflow"} or f["event_rate_per_10s"] > 5
    if trigger == "compositional_complexity":
        return f["object_complexity"] >= 2 and f["actions"] >= 4
    return False


def evaluate_knowledge(text: str, scene: dict, provider: str = "generic") -> list[EvidenceFinding]:
    features = extract_features(text, scene)
    packs = [load_pack("research")]
    if provider in {"veo", "runway"}:
        packs.insert(0, load_pack(provider))
    out: list[EvidenceFinding] = []
    for pack in packs:
        agent = f"Knowledge Scout · {pack.get('name', provider)}"
        for rule in pack.get("rules", []) or []:
            if not _triggered(str(rule.get("trigger", "")), features):
                continue
            out.append(EvidenceFinding(
                rule_id=str(rule.get("id")),
                agent=agent,
                severity=str(rule.get("severity", "warning")),
                message=str(rule.get("title", rule.get("id"))),
                recommendation=str(rule.get("recommendation", "")),
                points=int(rule.get("points", 0) or 0),
                sources=list(rule.get("sources", []) or []),
            ))
    return out
