#!/usr/bin/env python3
import subprocess
from pathlib import Path
import argparse
import yaml

from src.aggregator.aggregator import collect_posts
from src.agent.client import make_client
from src.agent.router import summarize_post
from src.report.render import render_digest

# Optional delivery helpers (introduced in future refactor). If missing, we skip gracefully.
try:
    from src.report.delivery import deliver_to_icloud, deliver_to_apple_notes  # type: ignore
except Exception:  # module may not exist yet
    deliver_to_icloud = None  # type: ignore
    deliver_to_apple_notes = None  # type: ignore

def main():
    ap = argparse.ArgumentParser(description="Stay Up To Date Agent (blogs MVP)")
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--limit", type=int, default=50, help="max posts to include in this run (global cap)")
    ap.add_argument("--yt-per-channel", type=int, default=None, help="cap videos per YouTube channel before the global limit (default 5 if not set)")
    ap.add_argument("--blog-per-source", type=int, default=None, help="cap blog posts per source before the global limit (default 2 if not set)")

    # Output/delivery options (CLI overrides for config)
    ap.add_argument("--out-dir", default=None, help="override output directory for rendered files")
    ap.add_argument("--formats", default=None, help="comma-separated list of formats to generate (html,md)")
    ap.add_argument("--icloud", dest="icloud", action=argparse.BooleanOptionalAction, default=None,
                    help="enable/disable iCloud copy of HTML (if delivery helper is available)")
    ap.add_argument("--notes", dest="notes", action=argparse.BooleanOptionalAction, default=None,
                    help="enable/disable Apple Notes update (if delivery helper is available)")
    ap.add_argument("--notes-title", dest="notes_title", default=None,
                    help="Apple Notes title template; {date} expands to YYYY-MM-DD")
    args = ap.parse_args()

    config_path = Path(args.config)
    # Collect without marking seen yet; we'll mark only summarized items later
    posts, cfg, storage_dir = collect_posts(config_path, mark_seen_immediately=False)

    # Merge output options: defaults <- config <- CLI
    output_defaults = {
        "save_dir": None,             # fallback handled inside renderer (data/reports)
        "formats": ["html"],         # default format
        "ios": {
            "icloud": {"enabled": False, "folder": "BlogDigest"},
            "notes": {"enabled": False, "title_template": "Daily Digest — {date}"},
        },
    }
    cfg_output = dict(output_defaults)
    cfg_output.update(cfg.get("output", {}) or {})
    # normalize nested dicts
    cfg_output.setdefault("ios", {}).setdefault("icloud", {}).setdefault("enabled", output_defaults["ios"]["icloud"]["enabled"])
    cfg_output.setdefault("ios", {}).setdefault("icloud", {}).setdefault("folder", output_defaults["ios"]["icloud"]["folder"])
    cfg_output.setdefault("ios", {}).setdefault("notes", {}).setdefault("enabled", output_defaults["ios"]["notes"]["enabled"])
    cfg_output.setdefault("ios", {}).setdefault("notes", {}).setdefault("title_template", output_defaults["ios"]["notes"]["title_template"])

    # Apply CLI overrides if provided
    if args.out_dir is not None:
        cfg_output["save_dir"] = args.out_dir
    if args.formats:
        cfg_output["formats"] = [f.strip() for f in args.formats.split(",") if f.strip()]
    if args.icloud is not None:
        cfg_output["ios"]["icloud"]["enabled"] = bool(args.icloud)
    if args.notes is not None:
        cfg_output["ios"]["notes"]["enabled"] = bool(args.notes)
    if args.notes_title:
        cfg_output["ios"]["notes"]["title_template"] = args.notes_title

    # Canonicalize formats and filter/sanitize
    wanted_formats = {fmt.lower() for fmt in (cfg_output.get("formats") or ["html"]) if fmt}
    valid_formats = {"html", "md"}
    # Allow a special "notes" format for Apple Notes-friendly HTML
    valid_formats |= {"notes"}
    wanted_formats = [f for f in wanted_formats if f in valid_formats]
    if not wanted_formats:
        wanted_formats = ["html"]

    # Apply optional per-source caps before global cap
    src_cfg = (cfg.get("sources", {}) or {})
    yt_cap = args.yt_per_channel if args.yt_per_channel is not None else int(src_cfg.get("youtube_per_channel_limit", 5))
    blog_cap = args.blog_per_source if args.blog_per_source is not None else int(src_cfg.get("blog_per_source_limit", 2))

    if (yt_cap and yt_cap > 0) or (blog_cap and blog_cap > 0):
        videos_by_key = {}
        blogs_by_key = {}
        others = []
        for p in posts:
            kind = p.get("kind")
            key = p.get("source_key")
            if kind == "video" and key:
                videos_by_key.setdefault(key, []).append(p)
            elif kind == "blog" and key:
                blogs_by_key.setdefault(key, []).append(p)
            else:
                others.append(p)

        capped = []
        if yt_cap and yt_cap > 0:
            for key, lst in videos_by_key.items():
                lst_sorted = sorted(lst, key=lambda x: x.get("published", ""), reverse=True)
                capped.extend(lst_sorted[:yt_cap])
        else:
            for lst in videos_by_key.values():
                capped.extend(lst)

        if blog_cap and blog_cap > 0:
            for key, lst in blogs_by_key.items():
                lst_sorted = sorted(lst, key=lambda x: x.get("published", ""), reverse=True)
                capped.extend(lst_sorted[:blog_cap])
        else:
            for lst in blogs_by_key.values():
                capped.extend(lst)

        posts = others + capped

    # take newest first, then apply global limit
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

    # After summarization, mark only summarized items as seen and persist state
    try:
        from src.util.state import load_state, save_state, mark_seen
        state_path = storage_dir / "state.json"
        state = load_state(state_path)
        # mark seen per source_key for exactly the items we summarized
        by_key = {}
        for it in items:
            post = it.get("post", {})
            key = post.get("source_key")
            pid = post.get("id")
            if key and pid:
                by_key.setdefault(key, []).append(pid)
        for k, ids in by_key.items():
            mark_seen(state, k, ids)
        save_state(state_path, state)
    except Exception:
        pass

    # Render with configured formats and optional out_dir
    out_dir = Path(cfg_output["save_dir"]).expanduser() if cfg_output.get("save_dir") else None
    # If Apple Notes delivery is enabled, ensure we also render the Notes HTML
    if cfg_output["ios"]["notes"]["enabled"]:
        if "notes" not in wanted_formats:
            wanted_formats.append("notes")

    md_path, html_path = render_digest(
        items,
        storage_dir,
        formats=tuple(wanted_formats),
        out_dir=out_dir,
    )

    # Report what we produced in a stable way
    produced = {}
    if html_path:
        produced["html"] = str(html_path)
    if md_path:
        produced["md"] = str(md_path)
    if produced:
        print("[update_agent] Wrote:")
        for k, v in produced.items():
            print(f"  - {k}: {v}")
    else:
        print("[update_agent] Nothing was rendered (no formats enabled or render failed).")

    # Optional: iOS deliveries (only if helpers are available and HTML exists)
    today = None
    try:
        from datetime import date as _date
        today = _date.today().isoformat()
    except Exception:
        today = None

    if html_path:
        # iCloud copy
        if cfg_output["ios"]["icloud"]["enabled"]:
            if deliver_to_icloud:
                try:
                    folder = cfg_output["ios"]["icloud"].get("folder", "BlogDigest")
                    deliver_to_icloud(html_path, folder)
                    print(f"[update_agent] iCloud copy updated: folder={folder}")
                except Exception as e:
                    print(f"[update_agent] iCloud delivery failed: {e}")
            else:
                print("[update_agent] iCloud delivery requested but helper not available; skipping.")
        # Apple Notes
        if cfg_output["ios"]["notes"]["enabled"]:
            if deliver_to_apple_notes:
                try:
                    title_tmpl = cfg_output["ios"]["notes"].get("title_template", "Daily Digest — {date}")
                    title = title_tmpl.format(date=today or "")
                    # Prefer the Apple Notes-friendly HTML if it was rendered
                    notes_candidate = (out_dir or (storage_dir / "reports")) / f"digest-notes-{today}.html"
                    deliver_path = notes_candidate if notes_candidate.exists() else html_path
                    deliver_to_apple_notes(deliver_path, title)
                    print(f"[update_agent] Apple Notes updated: '{title}'")
                except Exception as e:
                    print(f"[update_agent] Apple Notes delivery failed: {e}")
            else:
                print("[update_agent] Apple Notes delivery requested but helper not available; skipping.")

    # Auto-open HTML only if we actually have one and user likely expects local viewing
    if html_path:
        try:
            subprocess.run(["open", str(html_path)], check=False)
        except Exception:
            pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
