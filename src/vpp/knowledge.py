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
    evidence_tier: str = "B"
    provider_scope: str = "generic"

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
    if trigger == "exact_text_morph":
        return f.get("exact_text_morph", False)
    if trigger == "exact_text_present":
        return f.get("exact_text_present", False)
    if trigger == "camera_motion_overload":
        return f.get("camera_moves", 0) >= 3
    if trigger == "static_camera_request":
        return f.get("static_camera", False)
    if trigger == "multi_speaker_dialogue":
        return f.get("multi_speaker_dialogue", False)
    if trigger == "json_prompt":
        return f.get("json_like", False)
    if trigger == "image_to_video_prompt":
        return f.get("image_to_video_hint", False)
    if trigger == "minimax_camera_without_command":
        return f.get("has_camera", False) and not f.get("minimax_camera_command", False)
    if trigger == "more_than_four_subjects":
        return f.get("subject_count_hint", 0) > 4
    if trigger == "high_motion_request":
        return f.get("high_motion_hint", False)
    if trigger == "multi_shot_prompt":
        return f.get("multi_shot", False)
    return False


def evaluate_knowledge(text: str, scene: dict, provider: str = "generic") -> list[EvidenceFinding]:
    features = extract_features(text, scene)
    packs = [load_pack("constitution"), load_pack("research")]
    provider_pack = load_pack(provider)
    if provider != "generic" and provider_pack.get("rules"):
        packs.insert(1, provider_pack)

    out: list[EvidenceFinding] = []
    seen: set[tuple[str, str]] = set()
    for pack in packs:
        agent = f"Knowledge Scout · {pack.get('name', provider)}"
        pack_scope = str(pack.get("provider", "generic"))
        pack_tier = str(pack.get("evidence_tier", "B"))
        for rule in pack.get("rules", []) or []:
            if not _triggered(str(rule.get("trigger", "")), features):
                continue
            key = (str(rule.get("id")), pack_scope)
            if key in seen:
                continue
            seen.add(key)
            out.append(EvidenceFinding(
                rule_id=str(rule.get("id")),
                agent=agent,
                severity=str(rule.get("severity", "warning")),
                message=str(rule.get("title", rule.get("id"))),
                recommendation=str(rule.get("recommendation", "")),
                points=int(rule.get("points", 0) or 0),
                sources=list(rule.get("sources", []) or []),
                evidence_tier=str(rule.get("evidence_tier", pack_tier)),
                provider_scope=str(rule.get("provider_scope", pack_scope)),
            ))
    return out
