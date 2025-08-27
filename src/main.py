#!/usr/bin/env python3
import subprocess
from pathlib import Path
import argparse
import yaml

from src.aggregator.aggregator import collect_posts
from src.agent.client import make_client
from src.agent.router import summarize_post
from src.report.render import render_digest

def main():
    ap = argparse.ArgumentParser(description="Stay Up To Date Agent (blogs MVP)")
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--limit", type=int, default=1, help="max posts to summarize this run")
    args = ap.parse_args()

    config_path = Path(args.config)
    posts, cfg, storage_dir = collect_posts(config_path)

    # take newest first, cap by --limit
    posts = sorted(posts, key=lambda p: p.get("published", ""), reverse=True)[: args.limit]
    if not posts:
        print("No new posts found.")
        return 0

    project_root = Path(__file__).resolve().parents[1]
    client = make_client(project_root)
    items = []
    for post in posts:
        item = summarize_post(post, client, Path(args.prompts), cfg.get("interests", ""))
        items.append(item)

    md_path, html_path = render_digest(items, storage_dir)
    print(f"Wrote digest:\n- {md_path}\n- {html_path}")

    # auto-open HTML
    try:
        subprocess.run(["open", str(html_path)], check=False)
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())