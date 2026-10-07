"""Data model: features read from a CAD part, and the PMI suggested for them."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

FEATURE_TYPES = {"planar_face", "bore", "pin_hole", "clearance_hole", "threaded_hole"}


@dataclass
class Feature:
    id: str
    type: str
    name: str = ""
    role: str = "general"            # e.g. mating, bearing_seat, general
    diameter: float | None = None
    depth: float | None = None
    fastener: str | None = None      # e.g. "M6" for clearance and threaded holes
    x: float | None = None           # position in the top view (mm from lower-left corner)
    y: float | None = None
    area_mm2: float | None = None    # planar faces


@dataclass
class Part:
    name: str
    material: str
    width: float
    height: float
    thickness: float
    features: list[Feature]

    @staticmethod
    def from_json(path: str | Path) -> "Part":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        p, outline = data["part"], data["part"]["outline"]
        feats = []
        for f in data["features"]:
            if f["type"] not in FEATURE_TYPES:
                raise ValueError(f"Feature {f.get('id')}: unknown type '{f['type']}'")
            feats.append(Feature(**f))
        return Part(p["name"], p["material"], outline["width"], outline["height"], outline["thickness"], feats)


@dataclass
class Annotation:
    """One PMI item, attached to a feature. Kinds: datum, size, geometric, thread, surface, note."""
    feature_id: str
    kind: str
    text: str                        # how it reads on a drawing / in the NX PMI
    rule: str                        # which rule produced it (traceability)
    datum: str | None = None
    characteristic: str | None = None   # flatness, position, perpendicularity ...
    value: float | None = None
    modifier: str | None = None      # e.g. "MMC"
    refs: list[str] = field(default_factory=list)


@dataclass
class Finding:
    level: str                       # "error" or "warning"
    feature_id: str | None
    message: str


@dataclass
class PmiResult:
    part: Part
    annotations: list[Annotation]
    general_notes: list[str]
    findings: list[Finding] = field(default_factory=list)

    def for_feature(self, fid: str) -> list[Annotation]:
        return [a for a in self.annotations if a.feature_id == fid]

    def to_dict(self) -> dict:
        """Structured, validated output for downstream tools and AI agents."""
        feats = []
        for f in self.part.features:
            feats.append({
                "id": f.id, "type": f.type, "name": f.name, "role": f.role,
                "pmi": [{k: v for k, v in asdict(a).items() if v not in (None, [])}
                        for a in self.for_feature(f.id)],
            })
        return {
            "schema": "pmi-assistant/1.0",
            "part": {"name": self.part.name, "material": self.part.material,
                     "outline_mm": [self.part.width, self.part.height, self.part.thickness]},
            "datum_reference_frame": sorted({a.datum for a in self.annotations if a.datum}),
            "general_notes": self.general_notes,
            "features": feats,
            "validation": {
                "passed": not any(x.level == "error" for x in self.findings),
                "findings": [asdict(x) for x in self.findings],
            },
            "agent_summary": self.agent_summary(),
        }

    def agent_summary(self) -> str:
        """Short plain-text context an AI agent can use without parsing the whole file."""
        n_err = sum(x.level == "error" for x in self.findings)
        n_warn = sum(x.level == "warning" for x in self.findings)
        datums = ", ".join(f"{a.datum} = {a.feature_id}" for a in self.annotations if a.datum)
        return (f"Part '{self.part.name}' ({self.part.material}), {len(self.part.features)} features, "
                f"{len(self.annotations)} PMI annotations. Datums: {datums}. "
                f"Validation: {n_err} errors, {n_warn} warnings.")
