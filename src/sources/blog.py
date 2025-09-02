from __future__ import annotations
from pathlib import Path
from typing import List
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparse
import trafilatura

from .base import Post

def _discover_feed(homepage_url, headers):
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
                        from urllib.parse import urljoin
                        return urljoin(homepage_url, href)
    except Exception:
        pass
    return None

def _extract_markdown(url: str) -> str | None:
    html = trafilatura.fetch_url(url)
    if not html:
        return None
    md = trafilatura.extract(html, output_format="markdown") or trafilatura.extract(html)
    return md

def fetch_new(config_entry: dict, state: dict, ua: str) -> List[Post]:
    """
    config_entry: {key, feed?, homepage?, substack?, enabled?}
    - If `feed` is provided, it is used as-is.
    - Else if `substack` is provided (e.g., "https://coolai.substack.com"), the feed URL is computed as `<substack>/feed`.
    - Else if `homepage` looks like a Substack (e.g., contains ".substack.com"), the feed URL is computed as `<homepage>/feed`.
    - Else fallback to auto-discovery via `_discover_feed`.
    """
    key = config_entry["key"]
    if not config_entry.get("enabled", True):
        return []

    headers = {"User-Agent": ua, "Accept": "application/xml, text/html;q=0.9,*/*;q=0.8"}
    feed_url = config_entry.get("feed")
    if not feed_url:
        substack_home = config_entry.get("substack")
        if substack_home:
            feed_url = substack_home.rstrip("/") + "/feed"
    if not feed_url:
        homepage = config_entry.get("homepage", "")
        if homepage and ".substack.com" in homepage:
            feed_url = homepage.rstrip("/") + "/feed"
    if not feed_url:
        # Fallback: try to discover from homepage links
        feed_url = _discover_feed(config_entry.get("homepage", ""), headers)
    if not feed_url:
        return []

    d = feedparser.parse(feed_url, request_headers=headers)
    entries = d.entries or []
    # oldest→newest so content is saved chronologically
    entries.sort(key=lambda e: dateparse.parse(getattr(e, "published", getattr(e, "updated", "1970-01-01")))
                if getattr(e, "published", None) or getattr(e, "updated", None) else time.gmtime(0))

    seen_ids = set(state.get("seen_ids", {}).get(key, []))
    new_posts: List[Post] = []
    for e in entries:
        eid = getattr(e, "id", None) or getattr(e, "link", None)
        if not eid or eid in seen_ids:
            continue
        title = getattr(e, "title", "Untitled")
        url = getattr(e, "link", None) or ""
        published = getattr(e, "published", getattr(e, "updated", "")) or ""
        md = _extract_markdown(url) if url else None
        text = md or ""
        new_posts.append(Post(
            id=eid, 
            kind="blog", 
            source_key=key, 
            title=title, 
            url=url,
            published=published, 
            author=None, 
            text=text, 
            metadata={
                "display_name": config_entry.get("display_name", key)
            }
        ))
    return new_posts