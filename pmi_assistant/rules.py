"""Rule engine: turns recognised features into suggested PMI.

Every annotation records the rule that created it, so a designer can see why it was suggested.
Numeric defaults (flatness, roughness, bore position) live in RULESET and can be changed per company.
"""
from __future__ import annotations

from .model import Annotation, Feature, Finding, Part, PmiResult
from . import standards as iso

RULESET = {
    "general_class": "m",          # ISO 2768-1 tolerance class for untoleranced sizes
    "mating_flatness": 0.05,
    "bearing_position": 0.02,
    "datum_perpendicularity": 0.02,
    "pin_position": 0.05,
    "ra_bearing": 0.8,
    "ra_pin": 0.8,
    "ra_mating": 1.6,
    "ra_general": 3.2,
}


def hole_diameter(f: Feature) -> float | None:
    """Effective hole diameter used for geometry checks and drawing."""
    if f.type == "clearance_hole" and f.fastener in iso.CLEARANCE_MEDIUM:
        return iso.CLEARANCE_MEDIUM[f.fastener]
    if f.type == "threaded_hole" and f.fastener in iso.THREAD_NOMINAL:
        return iso.THREAD_NOMINAL[f.fastener]
    return f.diameter


def choose_datums(part: Part) -> dict[str, str]:
    """A = largest mating planar face; B, C = locating pin holes (B falls back to a bearing seat)."""
    datums: dict[str, str] = {}
    faces = [f for f in part.features if f.type == "planar_face" and f.role == "mating"]
    if faces:
        datums["A"] = max(faces, key=lambda f: f.area_mm2 or 0).id
    pins = [f for f in part.features if f.type == "pin_hole"]
    seats = [f for f in part.features if f.type == "bore" and f.role == "bearing_seat"]
    secondary = pins + seats
    if secondary:
        datums["B"] = secondary[0].id
    if len(pins) >= 2:
        datums["C"] = pins[1].id
    return datums


def _fmt(v: float) -> str:
    return f"{v:g}"


def _refs(datums: dict[str, str], exclude: str | None = None, upto: str = "C") -> list[str]:
    order = [d for d in "ABC" if d in datums and d <= upto]
    return [d for d in order if datums[d] != exclude]


def generate(part: Part, ruleset: dict | None = None) -> PmiResult:
    r = {**RULESET, **(ruleset or {})}
    datums = choose_datums(part)
    datum_of = {fid: d for d, fid in datums.items()}
    out: list[Annotation] = []
    findings: list[Finding] = []

    for f in part.features:
        d = datum_of.get(f.id)
        if d:
            out.append(Annotation(f.id, "datum", f"Datum {d}", "datum selection", datum=d))

        if f.type == "planar_face":
            if f.role == "mating":
                t = r["mating_flatness"]
                out.append(Annotation(f.id, "geometric", f"Flatness {_fmt(t)}", "mating face flatness",
                                      characteristic="flatness", value=t))
                out.append(Annotation(f.id, "surface", f"Ra {_fmt(r['ra_mating'])}", "mating face roughness",
                                      value=r["ra_mating"]))
            else:
                out.append(Annotation(f.id, "note", f"General tolerances ISO 2768-{r['general_class']}K",
                                      "general tolerance"))

        elif f.type in ("bore", "pin_hole"):
            dia = f.diameter
            precise = f.type == "pin_hole" or f.role == "bearing_seat"
            if precise:
                try:
                    up, lo = iso.h7_deviations(dia)
                    out.append(Annotation(f.id, "size", f"Ø{_fmt(dia)} H7 (+{up:.3f}/0)",
                                          "ISO 286 H7 fit for locating/bearing bores", value=dia))
                except ValueError as e:
                    findings.append(Finding("error", f.id, str(e)))
                ra = r["ra_pin"] if f.type == "pin_hole" else r["ra_bearing"]
                out.append(Annotation(f.id, "surface", f"Ra {_fmt(ra)}", "precision bore roughness", value=ra))
                if d in ("B",):
                    t = r["datum_perpendicularity"]
                    out.append(Annotation(f.id, "geometric", f"Perpendicularity Ø{_fmt(t)} | A",
                                          "secondary datum oriented to A", characteristic="perpendicularity",
                                          value=t, refs=_refs(datums, upto="A")))
                else:
                    t = r["pin_position"] if f.type == "pin_hole" else r["bearing_position"]
                    refs = _refs(datums, exclude=f.id, upto="B" if d == "C" else "C")
                    out.append(Annotation(f.id, "geometric", f"Position Ø{_fmt(t)} | {'|'.join(refs)}",
                                          "locate precision bore to datum frame", characteristic="position",
                                          value=t, refs=refs))
            else:
                tol = iso.iso2768_linear(dia, r["general_class"])
                out.append(Annotation(f.id, "size", f"Ø{_fmt(dia)} ±{_fmt(tol)}", "ISO 2768-1 general tolerance",
                                      value=dia))

        elif f.type == "clearance_hole":
            if f.fastener not in iso.CLEARANCE_MEDIUM:
                findings.append(Finding("error", f.id, f"Unknown fastener '{f.fastener}'"))
                continue
            h = iso.CLEARANCE_MEDIUM[f.fastener]
            up = iso.h13_upper(h)
            t = iso.floating_fastener_position_tol(f.fastener)
            refs = _refs(datums)
            out.append(Annotation(f.id, "size", f"Ø{_fmt(h)} H13 (+{_fmt(up)}/0) (clearance {f.fastener})",
                                  "ISO 273 medium clearance hole, H13 so that MMC = nominal", value=h))
            out.append(Annotation(f.id, "geometric", f"Position Ø{_fmt(t)} (M) | {'|'.join(refs)}",
                                  "floating fastener T = H - F", characteristic="position", value=t,
                                  modifier="MMC", refs=refs))

        elif f.type == "threaded_hole":
            if f.fastener not in iso.THREAD_NOMINAL:
                findings.append(Finding("error", f.id, f"Unknown thread '{f.fastener}'"))
                continue
            depth = f" ↧{_fmt(f.depth)}" if f.depth else ""
            t = iso.fixed_fastener_position_tol(f.fastener)
            refs = _refs(datums)
            out.append(Annotation(f.id, "thread", f"{f.fastener}-6H{depth}", "ISO 965 default thread class 6H"))
            out.append(Annotation(f.id, "geometric", f"Position Ø{_fmt(t)} (P) | {'|'.join(refs)}",
                                  "fixed fastener T = (H - F) / 2 with projected tolerance zone "
                                  "(zone height = mating part thickness)", characteristic="position", value=t,
                                  modifier="projected", refs=refs))

    notes = [
        f"General tolerances ISO 2768-{r['general_class']}K",
        f"Surface roughness unless otherwise specified: Ra {_fmt(r['ra_general'])}",
        "Dimensions in mm",
    ]
    return PmiResult(part, out, notes, findings)
