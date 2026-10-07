"""Static HTML report: annotated top view (SVG), PMI table and validation results for each part."""
from __future__ import annotations

import html
import json

from .model import PmiResult
from .rules import hole_diameter

TYPE_LABEL = {"planar_face": "Planar face", "bore": "Bore", "pin_hole": "Pin hole",
              "clearance_hole": "Clearance hole", "threaded_hole": "Threaded hole"}


def _svg(res: PmiResult, view_w: int = 640) -> str:
    p = res.part
    pad = 46
    s = (view_w - 2 * pad) / p.width
    view_h = int(p.height * s + 2 * pad)
    X = lambda x: pad + x * s
    Y = lambda y: pad + (p.height - y) * s          # CAD y-axis points up
    datum_of = {a.feature_id: a.datum for a in res.annotations if a.datum}
    warn_ids = {f.feature_id for f in res.findings if f.feature_id}

    o = [f'<svg viewBox="0 0 {view_w} {view_h}" role="img" aria-label="Top view of {html.escape(p.name)}">']
    o.append(f'<rect class="outline" x="{X(0)}" y="{Y(p.height)}" width="{p.width * s}" height="{p.height * s}" rx="3"/>')
    # overall dimensions
    o.append(f'<text class="dim" x="{X(p.width / 2)}" y="{Y(0) + 30}" text-anchor="middle">{p.width:g}</text>')
    o.append(f'<text class="dim" x="{X(0) - 26}" y="{Y(p.height / 2)}" text-anchor="middle" '
             f'transform="rotate(-90 {X(0) - 26} {Y(p.height / 2)})">{p.height:g}</text>')

    for f in p.features:
        if f.type == "planar_face" and datum_of.get(f.id):
            # face seen in plan: datum feature symbol on a leader ending in a dot on the face
            dx, dy = X(p.width * 0.72), Y(p.height * 0.3)
            bx, by = X(p.width) - 18, Y(0) + 8
            o.append(f'<circle class="datum-dot" cx="{dx:.1f}" cy="{dy:.1f}" r="3"/>')
            o.append(f'<line class="datum-line" x1="{dx:.1f}" y1="{dy:.1f}" x2="{bx:.1f}" y2="{by:.1f}"/>')
            o.append(f'<rect class="datum-box" x="{bx:.1f}" y="{by:.1f}" width="18" height="18"/>')
            o.append(f'<text class="datum-txt" x="{bx + 9:.1f}" y="{by + 13:.1f}" text-anchor="middle">{datum_of[f.id]}</text>')
            o.append(f'<text class="dim" x="{bx - 6:.1f}" y="{by + 13:.1f}" text-anchor="end">{html.escape(f.name.lower())}</text>')
            continue
        if f.x is None:
            continue
        d = hole_diameter(f) or 0
        r = max(d * s / 2, 3)
        cx, cy = X(f.x), Y(f.y)
        cls = f"hole {f.type}" + (" warn" if f.id in warn_ids else "")
        o.append(f'<g class="feat" data-fid="{f.id}">')
        o.append(f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"/>')
        if f.type == "threaded_hole":
            o.append(f'<circle class="thread-ring" cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 1.25:.1f}"/>')
        o.append(f'<line class="cmark" x1="{cx - r - 4:.1f}" y1="{cy:.1f}" x2="{cx + r + 4:.1f}" y2="{cy:.1f}"/>')
        o.append(f'<line class="cmark" x1="{cx:.1f}" y1="{cy - r - 4:.1f}" x2="{cx:.1f}" y2="{cy + r + 4:.1f}"/>')
        lx, ly = cx + r + 6, cy - r - 4
        o.append(f'<text class="fid" x="{lx:.1f}" y="{ly:.1f}">{f.id}</text>')
        if datum_of.get(f.id):
            bx, by = cx - r - 26, cy - r - 22
            o.append(f'<line class="datum-line" x1="{bx + 9}" y1="{by + 18}" x2="{cx - r * 0.7:.1f}" y2="{cy - r * 0.7:.1f}"/>')
            o.append(f'<rect class="datum-box" x="{bx:.1f}" y="{by:.1f}" width="18" height="18"/>')
            o.append(f'<text class="datum-txt" x="{bx + 9:.1f}" y="{by + 13:.1f}" text-anchor="middle">{datum_of[f.id]}</text>')
        o.append('</g>')
    o.append('</svg>')
    return "\n".join(o)


def _part_section(res: PmiResult, json_name: str) -> str:
    p = res.part
    rows = []
    for f in p.features:
        lines = "<br>".join(f"{html.escape(a.text)} <span class=\"rule\">({html.escape(a.rule)})</span>"
                            for a in res.for_feature(f.id))
        rows.append(f'<tr data-fid="{f.id}"><td>{f.id}</td><td>{html.escape(f.name)}<br>'
                    f'<span class="rule">{TYPE_LABEL[f.type]}</span></td><td>{lines}</td></tr>')
    findings = "".join(f"<li>{x.level.capitalize()}{' (' + x.feature_id + ')' if x.feature_id else ''}: "
                       f"{html.escape(x.message)}</li>" for x in res.findings) or "<li>No findings.</li>"
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in res.general_notes)
    anchor = json_name.replace(".pmi.json", "")
    return f"""
<section id="{anchor}">
  <h2>{html.escape(p.name)}</h2>
  <p class="meta">{html.escape(p.material)}, {p.width:g} x {p.height:g} x {p.thickness:g} mm</p>
  <div class="drawing">{_svg(res)}</div>
  <p class="meta">Top view. Blue circles are locating pin holes, dashed rings are threaded holes,
  orange marks a feature with a finding.</p>
  <h3>Validation</h3>
  <ul>{findings}</ul>
  <h3>General notes</h3>
  <ul>{notes}</ul>
  <h3>Suggested PMI</h3>
  <table><thead><tr><th>ID</th><th>Feature</th><th>PMI (rule)</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
  <p><a href="{json_name}">JSON output for this part</a></p>
</section>"""


CSS = """
body{margin:0;background:#fff;color:#111;font:15px/1.5 Arial,Helvetica,sans-serif}
.wrap{max-width:800px;margin:0 auto;padding:24px 16px 40px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:36px 0 2px;padding-top:16px;border-top:1px solid #ccc}
h3{font-size:16px;margin:20px 0 4px}
a{color:#0645ad}p{margin:8px 0}
.meta,.rule{color:#555;font-size:13px}
nav{margin:10px 0}nav a{margin-right:14px}
ul{margin:4px 0;padding-left:22px}
.drawing{border:1px solid #ccc;margin:10px 0 4px;overflow:hidden}
svg{width:100%;height:auto;display:block}
.outline{fill:#fff;stroke:#000;stroke-width:1.4}
.hole{fill:#fff;stroke:#000;stroke-width:1.2}.hole.pin_hole{stroke:#0645ad;stroke-width:1.6}
.hole.warn{stroke:#d35400;stroke-width:2}
.thread-ring{fill:none;stroke:#000;stroke-width:.8;stroke-dasharray:3 2}
.cmark{stroke:#888;stroke-width:.6;stroke-dasharray:6 2 1 2}
.fid{font:12px "Courier New",monospace;fill:#000}.dim{font:12px Arial,sans-serif;fill:#555}
.datum-box{fill:#fff;stroke:#000;stroke-width:1.1}.datum-txt{font:bold 12px Arial,sans-serif;fill:#000}
.datum-line{stroke:#000;stroke-width:.9}.datum-dot{fill:#000}
.feat.hl .hole{fill:#ffef9e}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{border:1px solid #bbb;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#eee}tr.hl td{background:#fffbe0}
td:first-child{font-family:"Courier New",monospace;white-space:nowrap}
footer{color:#555;font-size:13px;margin-top:36px;border-top:1px solid #ccc;padding-top:10px}
"""

JS = """
document.querySelectorAll('tr[data-fid]').forEach(tr=>{
  const g=()=>tr.closest('section').querySelector('.feat[data-fid="'+tr.dataset.fid+'"]');
  tr.addEventListener('mouseenter',()=>{tr.classList.add('hl');g()&&g().classList.add('hl')});
  tr.addEventListener('mouseleave',()=>{tr.classList.remove('hl');g()&&g().classList.remove('hl')});});
"""


def build_page(results: list[tuple[PmiResult, str]], repo_url: str) -> str:
    nav = "".join(f'<a href="#{j.replace(".pmi.json", "")}">{html.escape(r.part.name)}</a>' for r, j in results)
    sections = "".join(_part_section(r, j) for r, j in results)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PMI Assistant</title><style>{CSS}</style></head><body><div class="wrap">
<h1>PMI Assistant</h1>
<p>A small tool I wrote to suggest PMI for simple machined parts. It reads the features of a part
(faces, bores, pin holes, clearance and threaded holes), picks datums, suggests tolerances, GD&amp;T and surface
finish from ISO tables, checks the result and writes it to JSON. This page is generated from the two sample parts
in the repository.</p>
<p><a href="{repo_url}">Source code and README on GitHub</a></p>
<nav>Parts: {nav}</nav>
{sections}
<footer>Sample parts are made up for this demo. Sajin Saji, 2026.</footer>
</div><script>{JS}</script></body></html>"""
