from pathlib import Path
from datetime import date
from collections import defaultdict
from typing import Optional, Sequence, Tuple
from jinja2 import Template
from src.util.paths import ensure_dir

def render_digest(
    items,
    storage_dir: Path,
    *,
    formats: Sequence[str] = ("html",),
    out_dir: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """Render the daily digest.

    Parameters
    ----------
    items : list
        Aggregated items with summaries.
    storage_dir : Path
        Project storage directory; defaults for outputs derive from here.
    formats : sequence of {"html", "md"}
        Which formats to generate. Defaults to ("html",).
    out_dir : Path or None
        If provided, write outputs here; otherwise defaults to `storage_dir / "reports"`.

    Returns
    -------
    (md_path, html_path) : tuple[Optional[Path], Optional[Path]]
        Paths to files that were actually written (None if not generated).
    """
    today = date.today().isoformat()

    # Build summary stats grouped by (kind, display_name or source_key)
    groups = defaultdict(list)
    for it in items:
        post = it["post"]
        name = post.get("metadata", {}).get("display_name") or post.get("source_key")
        groups[(post.get("kind", ""), name)].append(it)

    stats = []
    for (kind, name), grp in groups.items():
        mt = None
        cap = None
        for it in grp:
            md = it["post"].get("metadata", {})
            if md.get("matched_total") is not None:
                mt = md.get("matched_total")
            if md.get("max_keep") is not None:
                cap = md.get("max_keep")
        stats.append({
            "kind": kind,
            "name": name,
            "shown": len(grp),
            "matched_total": mt,
            "cap": cap,
        })

    # Determine output directory
    reports_dir = Path(out_dir) if out_dir else (storage_dir / "reports")
    ensure_dir(reports_dir)

    fmtset = {f.lower() for f in formats}
    want_html = "html" in fmtset
    want_md = "md" in fmtset
    want_notes = "notes" in fmtset

    md_path: Optional[Path] = None
    html_path: Optional[Path] = None
    notes_path: Optional[Path] = None

    # Markdown (optional)
    if want_md:
        try:
            md_tpl_path = Path(__file__).parent / "templates" / "digest.md.j2"
            md_tpl = Template(md_tpl_path.read_text(encoding="utf-8"))
            md_out = md_tpl.render(date=today, items=items, stats=stats)
            md_path = reports_dir / f"digest-{today}.md"
            md_path.write_text(md_out, encoding="utf-8")
        except Exception as e:
            print(f"[render_digest] Markdown render skipped/failed: {e}")
            md_path = None

    # HTML (default)
    if want_html:
        try:
            html_tpl_path = Path(__file__).parent / "templates" / "digest.html.j2"
            html_tpl = Template(html_tpl_path.read_text(encoding="utf-8"))
            html_out = html_tpl.render(date=today, items=items, stats=stats)
            html_path = reports_dir / f"digest-{today}.html"
            html_path.write_text(html_out, encoding="utf-8")
        except Exception as e:
            print(f"[render_digest] HTML render failed: {e}")
            html_path = None

    # Apple Notes-friendly HTML (optional)
    if want_notes:
        try:
            notes_tpl_path = Path(__file__).parent / "templates" / "digest_notes.html.j2"
            notes_tpl = Template(notes_tpl_path.read_text(encoding="utf-8"))
            notes_out = notes_tpl.render(date=today, items=items)
            notes_path = reports_dir / f"digest-notes-{today}.html"
            notes_path.write_text(notes_out, encoding="utf-8")
        except Exception as e:
            print(f"[render_digest] Notes HTML render failed: {e}")
            notes_path = None

    return md_path, html_path
