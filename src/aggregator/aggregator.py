from typing import List
from pathlib import Path
import yaml

from src.sources.base import Post
from src.sources import blog as blog_src
from src.sources import youtube as yt_src
from src.sources import biorxiv as bio_src
from src.util.paths import resolve_storage_dir, ensure_dir
from src.util.state import load_state, save_state, mark_seen, have_seen

def collect_posts(config_path: Path, *, mark_seen_immediately: bool = True) -> tuple[list[Post], dict, Path]:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    storage_dir = resolve_storage_dir(cfg.get("storage_dir", "./data"))
    ensure_dir(storage_dir)

    state_path = storage_dir / "state.json"
    state = load_state(state_path)

    ua = cfg.get("user_agent", "StayUpToDate/0.1")
    results: List[Post] = []

    # blogs only (for MVP)
    for b in cfg.get("sources", {}).get("blogs", []):
        new_posts = blog_src.fetch_new(b, state, ua)
        if mark_seen_immediately:
            # immediately mark as seen so next run doesn't re-fetch
            mark_seen(state, b["key"], [p["id"] for p in new_posts])
        results.extend(new_posts)

    # youtube
    for y in cfg.get("sources", {}).get("youtube", []):
        new_posts = yt_src.fetch_new(y, state, ua)
        if mark_seen_immediately:
            mark_seen(state, y["key"], [p["id"] for p in new_posts])
        results.extend(new_posts)

    # bioRxiv
    for b in cfg.get("sources", {}).get("biorxiv", []):
        new_posts = bio_src.fetch_new(b, state, ua)
        if mark_seen_immediately:
            mark_seen(state, b["key"], [p["id"] for p in new_posts])
        results.extend(new_posts)

    if mark_seen_immediately:
        save_state(state_path, state)
    return results, cfg, storage_dir
