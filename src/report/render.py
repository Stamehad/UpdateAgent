from pathlib import Path
from datetime import date
from collections import defaultdict
from jinja2 import Template
from src.util.paths import ensure_dir

def render_digest(items, storage_dir: Path):
    today = date.today().isoformat()

    # Build summary stats grouped by (kind, display_name or source_key)
    groups = defaultdict(list)
    for it in items:
        post = it["post"]
        name = post.get("metadata", {}).get("display_name") or post.get("source_key")
        groups[(post.get("kind", ""), name)].append(it)

    stats = []
    for (kind, name), grp in groups.items():
        # Prefer matched_total/max_keep if present (bioRxiv), else infer
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

    # Markdown
    md_tpl = Template((Path(__file__).parent / "templates" / "digest.md.j2").read_text(encoding="utf-8"))
    md_out = md_tpl.render(date=today, items=items, stats=stats)
    md_path = storage_dir / f"digest-{today}.md"
    md_path.write_text(md_out, encoding="utf-8")

    # HTML
    html_tpl = Template((Path(__file__).parent / "templates" / "digest.html.j2").read_text(encoding="utf-8"))
    html_out = html_tpl.render(date=today, items=items, stats=stats)
    reports_dir = storage_dir / "reports"
    ensure_dir(reports_dir)
    html_path = reports_dir / f"digest-{today}.html"
    html_path.write_text(html_out, encoding="utf-8")
    return md_path, html_path

# def render_digest(items, storage_dir: Path):
#     today = date.today().isoformat()
#     # Markdown
#     md_tpl = Template((Path(__file__).parent / "templates" / "digest.md.j2").read_text(encoding="utf-8"))
#     md_out = md_tpl.render(date=today, items=items)
#     md_path = storage_dir / f"digest-{today}.md"
#     md_path.write_text(md_out, encoding="utf-8")

#     # HTML
#     html_tpl = Template((Path(__file__).parent / "templates" / "digest.html.j2").read_text(encoding="utf-8"))
#     html_out = html_tpl.render(date=today, items=items)
#     reports_dir = storage_dir / "reports"
#     ensure_dir(reports_dir)
#     html_path = reports_dir / f"digest-{today}.html"
#     html_path.write_text(html_out, encoding="utf-8")
#     return md_path, html_path