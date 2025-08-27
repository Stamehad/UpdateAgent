from __future__ import annotations
from typing import List
import feedparser
from dateutil import parser as dateparse
from .base import Post

def _get_media_description(entry) -> str:
    # YouTube places description under media:group/media:description
    # feedparser exposes it in entry.media_description or via entry.media_* attrs.
    desc = getattr(entry, "media_description", None)
    if desc:
        return str(desc)
    # Fallbacks
    if hasattr(entry, "summary"):
        return entry.summary
    return ""

def _entry_id(entry):
    return getattr(entry, "yt_videoid", None) or getattr(entry, "id", None) or getattr(entry, "link", None)

def fetch_new(config_entry: dict, state: dict, ua: str) -> List[Post]:
    """
    config_entry: {key, feed?, id?, enabled?, digest_mode?, display_name?}
    - If `feed` is provided, it is used as-is.
    - Else if `id` (YouTube channel_id, e.g. "UCawZsQWqfGSbCI5yjkdVkTA") is provided, the feed URL is computed as:
      https://www.youtube.com/feeds/videos.xml?channel_id=<id>
    """
    key = config_entry["key"]
    if not config_entry.get("enabled", True):
        return []

    # Allow either a full feed URL or a channel id
    feed_url = config_entry.get("feed")
    if not feed_url:
        channel_id = config_entry.get("id") or config_entry.get("channel_id")
        if channel_id:
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    if not feed_url:
        # nothing to do if neither feed nor id is provided
        return []

    headers = {"User-Agent": ua, "Accept": "application/atom+xml, application/xml;q=0.9,*/*;q=0.8"}
    d = feedparser.parse(feed_url, request_headers=headers)

    seen_ids = set(state.get("seen_ids", {}).get(key, []))
    posts: List[Post] = []
    for e in d.entries or []:
        vid = _entry_id(e)
        if not vid or vid in seen_ids:
            continue
        title = getattr(e, "title", "Untitled")
        url = getattr(e, "link", "")
        published = getattr(e, "published", getattr(e, "updated", "")) or ""
        raw_desc = _get_media_description(e)
        desc = clean_youtube_description(raw_desc)
        # Normalize
        posts.append(Post(
            id=vid,
            kind="video",
            source_key=key,
            title=title,
            url=url,
            published=published,
            author=getattr(e, "author", None),
            text=desc or "",
            metadata={
                "display_name": config_entry.get("display_name", key),
                "digest_mode": config_entry.get("digest_mode", "title_plus_description")
            }
        ))
    return posts

import re

PROMO_HINTS = (
    "sponsor", "sponsored", "subscribe", "newsletter", "discord", "patreon",
    "inquiries", "media/sponsorship", "affiliate", "promo", "my links", "links:"
)
SOCIAL_HINTS = ("x.com", "twitter.com", "instagram.com", "tiktok.com", "discord.gg", "discord.com", "linktr.ee", "bit.ly")
URL_RE = re.compile(r'https?://\S+')
TIMESTAMP_RE = re.compile(r'^\s*\d{1,2}:\d{2}(?::\d{2})?\b')

def clean_youtube_description(desc: str) -> str:
    if not desc:
        return ""
    # Split, strip, and drop empty lines
    lines = [ln.strip() for ln in desc.splitlines() if ln.strip()]
    cleaned = []
    skip_block = False
    for ln in lines:
        low = ln.lower()

        # Start of a “Links:” section → skip rest if it’s a pure link dump
        if low.startswith("links:") or low == "links":
            skip_block = True
            continue
        if skip_block:
            # Stop skipping if we reach a non-linky line
            if not (URL_RE.search(ln) or any(h in low for h in SOCIAL_HINTS)):
                skip_block = False
            else:
                continue

        # Drop pure links or lines that are mostly links
        if URL_RE.fullmatch(ln):
            continue
        if URL_RE.search(ln):
            # remove URLs and see what's left
            remainder = URL_RE.sub("", ln).strip()
            if remainder == "":
                continue

        # Drop obvious promo/social
        if any(h in low for h in PROMO_HINTS) or any(h in low for h in SOCIAL_HINTS):
            continue

        # Keep timestamps only if they carry a useful label (e.g., "10:20 Google AI Voice Assistant")
        if TIMESTAMP_RE.match(ln):
            # keep; the router may use timestamps to build Topics later
            cleaned.append(ln)
            continue

        cleaned.append(ln)

    # If the first lines are still noisy caps (views/date), drop the first line if it looks like that
    if cleaned and ("views" in cleaned[0].lower() and any(m.isdigit() for m in cleaned[0])):
        cleaned = cleaned[1:]

    # Collapse to a short paragraph
    paragraph = " ".join(cleaned)
    # Remove leftover inline URLs
    paragraph = URL_RE.sub("", paragraph)
    # Normalize spaces
    paragraph = re.sub(r'\s{2,}', ' ', paragraph).strip()

    # If it’s still huge, trim to ~350 chars (enough to hint content)
    return paragraph[:350]