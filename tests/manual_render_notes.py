"""
Manual helper to render a Daily Digest Notes HTML using mock items,
so you can verify Apple Notes hashtag rendering without running the
full pipeline or fetching new posts.

Usage (Notebook):

    from tests.manual_render_notes import render_test_notes
    html_path = render_test_notes(deliver=True)

This writes `data/reports/digest-notes-YYYY-MM-DD.html` and, if on macOS
with delivery helpers available, sends it to Apple Notes with a test title.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import date

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.render import render_digest

try:
    from src.report.delivery import deliver_to_apple_notes  # type: ignore
except Exception:
    deliver_to_apple_notes = None  # type: ignore


def _mock_items():
    today = date.today().isoformat()
    return [
        {
            "post": {
                "id": "blog1",
                "kind": "blog",
                "source_key": "test_blog",
                "title": "Test Blog Post",
                "url": "https://example.com/post",
                "published": today,
                "metadata": {"display_name": "Test Blog"},
            },
            "summary": "First line with key takeaways\n• Bullet one\n• Bullet two",
        },
        {
            "post": {
                "id": "vid1",
                "kind": "video",
                "source_key": "test_channel",
                "title": "Test Video",
                "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
                "published": today,
                "metadata": {"display_name": "Test Channel"},
            },
            "summary": "Intro\n• Highlight A\n• Highlight B",
        },
    ]


def render_test_notes(*, out_dir: Path | None = None, deliver: bool = False) -> Path:
    items = _mock_items()
    storage_dir = Path("./data").resolve()
    out_dir = Path(out_dir) if out_dir else Path("./data/reports").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Force Notes format only; renderer sets filename digest-notes-YYYY-MM-DD.html
    md_path, html_path = render_digest(items, storage_dir, formats=("notes",), out_dir=out_dir)
    notes_path = out_dir / f"digest-notes-{date.today().isoformat()}.html"

    if deliver and deliver_to_apple_notes:
        try:
            title = f"Daily Digest — {date.today().isoformat()} (TEST)"
            deliver_to_apple_notes(notes_path, title)
        except Exception as e:
            print(f"[manual_render_notes] Apple Notes delivery failed: {e}")
    elif deliver and not deliver_to_apple_notes:
        print("[manual_render_notes] Delivery helper not available; skipping Notes update.")

    return notes_path


if __name__ == "__main__":
    p = render_test_notes(deliver=False)
    print(f"Wrote: {p}")

