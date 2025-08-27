from __future__ import annotations
from typing import List
from datetime import date, timedelta
from urllib.parse import quote
import requests
import sys
import re

from .base import Post

API_BASE = "https://api.biorxiv.org/details/biorxiv"

def _daterange(days: int) -> tuple[str, str]:
    to = date.today()
    frm = to - timedelta(days=max(1, days))
    return frm.isoformat(), to.isoformat()

def _fetch_json(url: str, ua: str) -> dict:
    r = requests.get(url, headers={"User-Agent": ua, "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

def _match_keywords(txt: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    t = (txt or "").lower()
    for kw in keywords:
        if kw.strip() and kw.strip().lower() in t:
            return True
    return False

def fetch_new(config_entry: dict, state: dict, ua: str) -> List[Post]:
    """
    config_entry:
      {
        key, enabled, keywords: [..], days?: int (default 3),
        max_results?: int (api fetch window cap, default 200),
        max_keep?: int (after filtering; default 10),
        display_name?, digest_mode?
      }
    """
    key = config_entry["key"]
    if not config_entry.get("enabled", True):
        return []

    days = int(config_entry.get("days", 3))
    frm, to = _daterange(days)
    # API is paginated @ 100; we’ll just request the first chunk (max_results) for simplicity
    max_results = int(config_entry.get("max_results", 200))
    url = f"{API_BASE}/{frm}/{to}/0"  # cursor=0
    data = _fetch_json(url, ua)

    all_items = data.get("collection", []) or []
    if config_entry.get("debug"):
        print(f"[biorxiv:{key}] API window {frm}..{to} returned {len(all_items)} items (first page)", file=sys.stderr)

    # Local filter by keywords in title or abstract
    keywords = config_entry.get("keywords", [])
    seen_ids = set(state.get("seen_ids", {}).get(key, []))
    posts: List[Post] = []

    candidates = []
    for it in all_items[:max_results]:
        doi = it.get("doi")
        if not doi or doi in seen_ids:
            continue
        title = it.get("title", "Untitled")
        abstract = it.get("abstract", "") or ""
        if not (_match_keywords(title, keywords) or _match_keywords(abstract, keywords)):
            continue
        url_abs = f"https://www.biorxiv.org/content/{doi}"
        candidates.append({
            "doi": doi,
            "title": title,
            "abstract": abstract.strip(),
            "url": url_abs,
            "published": it.get("date", ""),
        })

    matched_total = len(candidates)
    max_keep = int(config_entry.get("max_keep", 10))
    # newest first
    candidates.sort(key=lambda x: x.get("published", ""), reverse=True)
    kept = candidates[:max_keep]

    posts: List[Post] = []
    for idx, c in enumerate(kept, start=1):
        posts.append(Post(
            id=c["doi"],
            kind="paper",
            source_key=key,
            title=c["title"],
            url=c["url"],
            published=c["published"],
            author=None,
            text=c["abstract"],
            metadata={
                "display_name": config_entry.get("display_name", key),
                "digest_mode": config_entry.get("digest_mode", "abstract_only"),
                "query": " ".join(keywords),
                "matched_total": matched_total,  # how many matched in window
                "kept_index": idx,               # 1-based index among kept
                "kept_total": len(kept),         # how many kept (<= max_keep)
                "max_keep": max_keep,            # the cap
            },
        ))

    if config_entry.get("debug"):
        print(f"[biorxiv:{key}] matched {matched_total}; keeping {len(kept)} (cap={max_keep})", file=sys.stderr)

    return posts

    # for it in all_items[:max_results]:
    #     doi = it.get("doi")
    #     if not doi or doi in seen_ids:
    #         continue
    #     title = it.get("title", "Untitled")
    #     abstract = it.get("abstract", "") or ""
    #     if not (_match_keywords(title, keywords) or _match_keywords(abstract, keywords)):
    #         continue

    #     url_abs = f"https://www.biorxiv.org/content/{doi}"
    #     posts.append(Post(
    #         id=doi,
    #         kind="paper",
    #         source_key=key,
    #         title=title,
    #         url=url_abs,
    #         published=it.get("date", ""),
    #         author=None,
    #         text=abstract.strip(),
    #         metadata={
    #             "display_name": config_entry.get("display_name", key),
    #             "digest_mode": config_entry.get("digest_mode", "abstract_only"),
    #             "query": " ".join(keywords),
    #         },
    #     ))

    # # Keep only the most recent N after filtering
    # max_keep = int(config_entry.get("max_keep", 10))
    # posts.sort(key=lambda p: p.get("published", ""), reverse=True)
    # posts = posts[:max_keep]

    # if config_entry.get("debug"):
    #     print(f"[biorxiv:{key}] matched {len(posts)} after keyword filter (keeping {max_keep})", file=sys.stderr)

    # return posts