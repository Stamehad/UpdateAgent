

from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path
from shutil import copyfile
from typing import Iterable, Optional, Tuple

from src.util.paths import ensure_dir


def _is_macos() -> bool:
    return os.uname().sysname == "Darwin"


def deliver_to_icloud(html_path: Path, folder: str = "BlogDigest") -> Tuple[Path, Path]:
    """Copy the rendered HTML to iCloud Drive for easy iPhone viewing.

    - Creates ~/Library/Mobile Documents/com~apple~CloudDocs/<folder>/
    - Writes a dated copy (digest-YYYY-MM-DD.html) and latest.html

    Returns
    -------
    (dated_copy, latest_copy)
        Paths to the two files in iCloud Drive.
    """
    if not _is_macos():
        raise RuntimeError("iCloud delivery is only supported on macOS.")

    if not isinstance(html_path, Path):
        html_path = Path(html_path)

    if not html_path.exists():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    today = date.today().isoformat()
    base = Path(os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs"))
    icloud_dir = base / folder
    ensure_dir(icloud_dir)

    dated_copy = icloud_dir / f"digest-{today}.html"
    latest_copy = icloud_dir / "latest.html"

    copyfile(html_path, dated_copy)
    copyfile(html_path, latest_copy)

    return dated_copy, latest_copy


def deliver_to_apple_notes(
    html_path: Path,
    note_title: str,
    tags: Optional[Iterable[str]] = ("#AI", "#DailyDigest"),
) -> None:
    """Create or overwrite a single Apple Notes note with the HTML digest.

    Parameters
    ----------
    html_path : Path to the rendered HTML file.
    note_title : Title of the note (e.g., "Daily Digest — 2025-09-01").
    tags : Optional iterable of hashtag strings to append at the end. A trailing
           space is added to help Notes auto-link hashtags.
    """
    if not _is_macos():
        raise RuntimeError("Apple Notes delivery is only supported on macOS.")

    if not isinstance(html_path, Path):
        html_path = Path(html_path)

    if not html_path.exists():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    # Prepare a safe path for embedding in JXA
    safe_path = str(html_path).replace("'", "\\'")

    tags_html = ""
    if tags:
        # Ensure a trailing space for Notes hashtag detection
        tags_line = " ".join(tags) + " "
        tags_html = f"<hr/><p>{tags_line}</p>"

    # JXA script: prefer iCloud account; create/overwrite note with given title
    jxa = f"""
    (() => {{
      ObjC.import('Foundation');
      const app = Application('Notes');
      app.includeStandardAdditions = true;
      const fm = Application.currentApplication(); fm.includeStandardAdditions = true;

      const p = '{safe_path}';
      const html = fm.doShellScript('cat ' + p.replace(/"/g,'\\"'));
      const taggedHtml = html + '\\n\\n' + `{tags_html}`;
      const desiredTitle = '{note_title.replace("'", "\\'")}';

      const accounts = app.accounts();
      const icloud = accounts.find(a => /icloud/i.test(a.name())) || accounts[0];
      const folders = icloud ? icloud.folders() : app.folders();
      const notesFolder = folders.find(f => f.name() === 'Notes') || folders[0];

      let note = notesFolder.notes().find(n => n.name() === desiredTitle);
      if (!note) {{
        note = app.Note({{name: desiredTitle, body: taggedHtml}});
        notesFolder.notes.push(note);
      }} else {{
        note.body = taggedHtml;
      }}
    }})();
    """

    subprocess.run(["osascript", "-l", "JavaScript", "-e", jxa], check=False)