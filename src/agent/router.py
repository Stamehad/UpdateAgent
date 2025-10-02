import logging
from pathlib import Path

from openai import OpenAI

from src.sources.base import Post

MODEL = "gpt-4o-mini"  # good $/quality
logger = logging.getLogger(__name__)

def load_prompt_texts(prompts_dir: Path, kind: str, interests: str) -> tuple[str, str]:
    system = (prompts_dir / f"{kind}_system.txt").read_text(encoding="utf-8")
    user_tmpl = (prompts_dir / f"{kind}_user.txt").read_text(encoding="utf-8")
    user = user_tmpl.format(interests=interests)
    return system, user

def summarize_post(post: Post, client: OpenAI, prompts_dir: Path, interests: str):
    if post["kind"] == "paper" and post.get("metadata", {}).get("digest_mode") == "abstract_only":
        abstract = (post.get("text") or "").strip()
        summary = abstract[:1200]  # keep digest readable; adjust if you like
        return {"post": post, "summary": summary}

    if post["kind"] == "video" and post.get("metadata", {}).get("digest_mode") in ("title_only", "title_plus_description"):
        # No LLM call: produce a compact summary based on title/description rules.
        desc = (post.get("text") or "").strip()
        if post["metadata"]["digest_mode"] == "title_only" or not desc:
            summary = "A new video is available."
        else:
            # Trim noisy lines (sponsor blocks, link dumps); keep a short paragraph
            lines = [ln.strip() for ln in desc.splitlines() if ln.strip()]
            # Heuristic: drop lines that are just links or “My Links” blocks
            keep = []
            for ln in lines:
                if ln.lower().startswith(("http://","https://")): 
                    continue
                if any(k in ln.lower() for k in ["sponsor", "discord", "newsletter", "subscribe", "links:", "my links"]):
                    continue
                keep.append(ln)
            collapsed = " ".join(keep)
            summary = collapsed[:500]  # keep it short; enough to hint topics
        return {"post": post, "summary": summary}

    # default path: use LLM with source-specific prompts
    system, user = load_prompt_texts(prompts_dir, post["kind"], interests)
    header = f"Title: {post['title']}\nURL: {post['url']}\n\n"
    body = (post.get("text") or "")
    text = header + body
    try:
        resp = client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "user", "content": text[:80_000]},
            ],
        )
        summary = resp.output_text
    except Exception:  # noqa: BLE001 - we want to keep digest generation resilient
        ident = post.get("url") or post.get("id") or post.get("title") or "unknown post"
        logger.exception("LLM summarization failed for %s; using fallback content", ident)
        summary = fallback_summary(post, body)
    return {"post": post, "summary": summary}


def fallback_summary(post: Post, body: str) -> str:
    paragraph = next((p.strip() for p in body.split("\n\n") if p.strip()), "")
    if paragraph:
        return paragraph[:1200]

    title = post.get("title") or ""
    url = post.get("url") or ""
    if title and url:
        return f"{title}\n{url}"
    if title:
        return title
    if url:
        return url
    return "Summary unavailable."


# def summarize_post(post: Post, client: OpenAI, prompts_dir: Path, interests: str) -> Dict:
#     system, user = load_prompt_texts(prompts_dir, post["kind"], interests)
#     header = f"Title: {post['title']}\nURL: {post['url']}\n\n"
#     text = header + (post.get("text") or "")
#     resp = client.responses.create(
#         model=MODEL,
#         input=[
#             {"role": "system", "content": system},
#             {"role": "user", "content": user},
#             {"role": "user", "content": text[:80_000]},
#         ],
#     )
#     return {"post": post, "summary": resp.output_text}
