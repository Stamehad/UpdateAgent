import json
from pathlib import Path
from .paths import ensure_dir

def load_state(state_path: Path) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"seen_ids": {}, "summarized_ids": {}}

def save_state(state_path: Path, state: dict):
    ensure_dir(state_path.parent)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path)

def mark_seen(state: dict, bucket: str, ids):
    seen = set(state["seen_ids"].get(bucket, []))
    seen.update(ids)
    state["seen_ids"][bucket] = sorted(list(seen))[-2000:]

def have_seen(state: dict, bucket: str, _id: str) -> bool:
    return _id in set(state["seen_ids"].get(bucket, []))