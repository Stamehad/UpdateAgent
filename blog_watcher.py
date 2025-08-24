#!/usr/bin/env python3
import argparse, json, os, re, sys, time
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparse
import yaml
import trafilatura

# ---------- utils ----------
def expand(p): return Path(os.path.expanduser(p)).resolve()

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_state(path: Path):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": {}}

def save_state(path: Path, state):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:100] or "post"

# ---------- feed discovery (fallbacks if feed not provided) ----------
def discover_feed(homepage_url, headers):
    try:
        r = requests.get(homepage_url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for link in soup.find_all("link"):
            if link.get("rel") and "alternate" in [x.lower() for x in link.get("rel")]:
                t = (link.get("type") or "").lower()
                if "rss" in t or "xml" in t or "atom" in t:
                    href = link.get("href")
                    if href:
                        return urljoin(homepage_url, href)
    except Exception:
        pass
    # common WordPress patterns
    for candidate in ("feed/", "?feed=rss2", "rss.xml", "atom.xml"):
        try:
            url = urljoin(homepage_url.rstrip("/") + "/", candidate)
            r = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
            if r.ok and "xml" in r.headers.get("content-type", "").lower():
                return r.url
        except Exception:
            continue
    return None

# ---------- download & save ----------
def extract_markdown(url):
    # Trafilatura returns plain text by default; try markdown if available.
    html = trafilatura.fetch_url(url)
    if not html:
        return None
    md = trafilatura.extract(html, output_format="markdown")
    if not md:
        md = trafilatura.extract(html)
    return md

def save_post(base_dir: Path, blog_key: str, title: str, url: str, published_iso: str, md_text: str):
    dt = dateparse.parse(published_iso) if published_iso else None
    y = str(dt.year if dt else "unknown")
    m = f"{dt.month:02d}" if dt else "00"
    folder = base_dir / "posts" / blog_key / y / m
    ensure_dir(folder)
    name = f"{dt.date() if dt else 'unknown'}-{slugify(title)}.md"
    path = folder / name
    frontmatter = [
        "---",
        f'title: "{title.replace("\"","\'")}"',
        f"source_url: {url}",
        f"blog: {blog_key}",
        f"published: {published_iso or ''}",
        "---",
        "",
    ]
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(frontmatter))
        f.write(md_text or "")
    return path

# ---------- main ----------
def process_blog(blog, state, storage_dir, headers):
    key = blog["key"]
    seen = set(state["seen_ids"].get(key, []))
    feed_url = blog.get("feed") or discover_feed(blog["homepage"], headers)
    if not feed_url:
        print(f"[{key}] No feed found; skipping.")
        return 0

    d = feedparser.parse(feed_url, request_headers=headers)
    if d.bozo:
        print(f"[{key}] Feed parse issue (bozo={d.bozo_exception}); continuing with best-effort.")
    entries = d.entries or []
    # sort oldest->newest so we save chronologically
    entries.sort(key=lambda e: dateparse.parse(getattr(e, "published", getattr(e, "updated", "1970-01-01"))) if getattr(e, "published", None) or getattr(e, "updated", None) else time.gmtime(0))

    new_count = 0
    base_dir = expand(storage_dir)
    ensure_dir(base_dir)

    for e in entries:
        eid = getattr(e, "id", None) or getattr(e, "link", None)
        if not eid or eid in seen:
            continue
        title = getattr(e, "title", "Untitled")
        url = getattr(e, "link", None)
        published = getattr(e, "published", getattr(e, "updated", ""))

        print(f"[{key}] NEW: {title}")
        md = extract_markdown(url) if url else None
        save_post(base_dir, key, title, url, published, md or "")
        seen.add(eid)
        new_count += 1

    state["seen_ids"][key] = sorted(list(seen))[-1000:]  # cap growth
    return new_count

def main():
    ap = argparse.ArgumentParser(description="Blog watcher (Stage 1)")
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--once", action="store_true", help="Run once (default).")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    storage_dir = cfg.get("storage_dir", "./data")
    ensure_dir(expand(storage_dir))
    state_path = expand(storage_dir) / "state.json"
    state = load_state(state_path)

    headers = {
        "User-Agent": cfg.get("user_agent", "BlogWatcher/0.1"),
        "Accept": "application/xml, text/xml, text/html;q=0.9,*/*;q=0.8",
    }

    total_new = 0
    for blog in cfg["blogs"]:
        if not blog.get("enabled", True):
            continue
        total_new += process_blog(blog, state, storage_dir, headers)

    save_state(state_path, state)
    print(f"Done. New posts saved: {total_new}")

if __name__ == "__main__":
    sys.exit(main())