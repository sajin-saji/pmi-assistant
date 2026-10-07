"""Checks run on the suggested PMI and on the part geometry before anything is written back to CAD."""
from __future__ import annotations

import math

from .model import Finding, PmiResult
from .rules import hole_diameter

HOLE_TYPES = {"bore", "pin_hole", "clearance_hole", "threaded_hole"}
FASTENER_HOLES = {"pin_hole", "clearance_hole", "threaded_hole"}


def validate(res: PmiResult, min_edge_factor: float = 1.5, min_web_mm: float = 2.0) -> PmiResult:
    part, f_out = res.part, res.findings
    datums = {a.datum: a.feature_id for a in res.annotations if a.datum}

    # Datum reference frame
    if "A" not in datums:
        f_out.append(Finding("error", None, "No primary datum A: the part has no mating planar face."))
    if "B" not in datums:
        f_out.append(Finding("warning", None, "No secondary datum B: add a locating pin hole or bearing seat."))
    if "C" not in datums:
        f_out.append(Finding("warning", None, "No tertiary datum C: rotation about B is not constrained."))

    # Every feature must carry PMI, and every datum reference must exist
    for f in part.features:
        if not res.for_feature(f.id):
            f_out.append(Finding("error", f.id, "Feature has no PMI."))
    for a in res.annotations:
        for ref in a.refs:
            if ref not in datums:
                f_out.append(Finding("error", a.feature_id, f"{a.characteristic} references undefined datum {ref}."))

    # Geometry checks on holes in the top view
    holes = [f for f in part.features if f.type in HOLE_TYPES and f.x is not None]
    for f in holes:
        d = hole_diameter(f) or 0
        if not (0 < f.x < part.width and 0 < f.y < part.height):
            f_out.append(Finding("error", f.id, "Hole centre lies outside the part outline."))
            continue
        edge = min(f.x, f.y, part.width - f.x, part.height - f.y)
        if f.type in FASTENER_HOLES and edge < min_edge_factor * d:
            f_out.append(Finding("warning", f.id,
                                 f"Edge distance {edge:g} mm is below {min_edge_factor} × Ø{d:g} = "
                                 f"{min_edge_factor * d:g} mm."))
        elif f.type == "bore" and edge - d / 2 < min_web_mm:
            f_out.append(Finding("warning", f.id, f"Wall to the outer edge is only {edge - d / 2:.1f} mm."))
    for i, a in enumerate(holes):
        for b in holes[i + 1:]:
            web = math.dist((a.x, a.y), (b.x, b.y)) - ((hole_diameter(a) or 0) + (hole_diameter(b) or 0)) / 2
            if web < min_web_mm:
                f_out.append(Finding("warning", a.id, f"Wall between {a.id} and {b.id} is only {web:.1f} mm."))
    return res
