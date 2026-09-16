from pathlib import Path
import json
import yaml


def load_scene(path: str) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def dump_scene(scene: dict, path: str) -> None:
    p = Path(path)
    if p.suffix.lower() == ".json":
        p.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        p.write_text(yaml.safe_dump(scene, allow_unicode=True, sort_keys=False), encoding="utf-8")
