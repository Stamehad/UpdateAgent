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
    ap.add_argument("--limit", type=int, default=1, help="max posts to summarize this run")

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
    posts, cfg, storage_dir = collect_posts(config_path)

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
    wanted_formats = [f for f in wanted_formats if f in valid_formats]
    if not wanted_formats:
        wanted_formats = ["html"]

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

    # Render with configured formats and optional out_dir
    out_dir = Path(cfg_output["save_dir"]).expanduser() if cfg_output.get("save_dir") else None
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
                    deliver_to_apple_notes(html_path, title)
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