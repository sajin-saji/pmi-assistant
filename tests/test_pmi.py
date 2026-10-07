"""Unit tests: standards tables, rule engine, validation and JSON output. Run: python -m unittest -v"""
import json
import unittest
from pathlib import Path

from pmi_assistant import standards as iso
from pmi_assistant.model import Feature, Part
from pmi_assistant.rules import choose_datums, generate
from pmi_assistant.validate import validate

ROOT = Path(__file__).resolve().parent.parent


def plate(**changes) -> Part:
    part = Part.from_json(ROOT / "samples" / "mounting_plate.json")
    for k, v in changes.items():
        setattr(part, k, v)
    return part


class TestStandards(unittest.TestCase):
    def test_iso2768_medium(self):
        self.assertEqual(iso.iso2768_linear(6.6, "m"), 0.2)
        self.assertEqual(iso.iso2768_linear(30, "m"), 0.2)    # 30 belongs to the >6..30 range
        self.assertEqual(iso.iso2768_linear(35, "m"), 0.3)
        self.assertEqual(iso.iso2768_linear(160, "f"), 0.2)

    def test_iso2768_out_of_range(self):
        with self.assertRaises(ValueError):
            iso.iso2768_linear(0.2)

    def test_h7(self):
        self.assertEqual(iso.h7_deviations(6), (0.012, 0.0))   # 6 belongs to >3..6
        self.assertEqual(iso.h7_deviations(35), (0.025, 0.0))
        self.assertEqual(iso.h7_deviations(10.5), (0.018, 0.0))

    def test_h13_clearance(self):
        self.assertEqual(iso.h13_upper(6.6), 0.22)
        self.assertEqual(iso.h13_upper(5.5), 0.18)

    def test_fastener_position(self):
        self.assertEqual(iso.floating_fastener_position_tol("M6"), 0.6)    # 6.6 - 6
        self.assertEqual(iso.fixed_fastener_position_tol("M5"), 0.25)      # (5.5 - 5) / 2


class TestRules(unittest.TestCase):
    def setUp(self):
        self.res = validate(generate(plate()))

    def test_datum_frame(self):
        self.assertEqual(choose_datums(self.res.part), {"A": "F1", "B": "P1", "C": "P2"})

    def test_every_feature_has_pmi(self):
        for f in self.res.part.features:
            self.assertTrue(self.res.for_feature(f.id), f.id)

    def test_bearing_seat_gets_h7_and_position(self):
        texts = [a.text for a in self.res.for_feature("H1")]
        self.assertIn("Ø35 H7 (+0.025/0)", texts)
        self.assertIn("Position Ø0.02 | A|B|C", texts)

    def test_clearance_hole_floating_fastener(self):
        pos = [a for a in self.res.for_feature("C1") if a.characteristic == "position"][0]
        self.assertEqual((pos.value, pos.modifier, pos.refs), (0.6, "MMC", ["A", "B", "C"]))

    def test_clearance_hole_is_h13_so_mmc_is_nominal(self):
        size = [a for a in self.res.for_feature("C1") if a.kind == "size"][0]
        self.assertTrue(size.text.startswith("Ø6.6 H13 (+0.22/0)"))

    def test_threaded_hole_uses_projected_zone(self):
        pos = [a for a in self.res.for_feature("T1") if a.characteristic == "position"][0]
        self.assertEqual((pos.value, pos.modifier), (0.25, "projected"))

    def test_datum_c_not_referenced_by_itself(self):
        pos = [a for a in self.res.for_feature("P2") if a.characteristic == "position"][0]
        self.assertEqual(pos.refs, ["A", "B"])

    def test_ruleset_override(self):
        res = generate(plate(), {"mating_flatness": 0.02})
        flat = [a for a in res.for_feature("F1") if a.characteristic == "flatness"][0]
        self.assertEqual(flat.value, 0.02)

    def test_unknown_fastener_is_reported(self):
        part = plate()
        part.features.append(Feature("C9", "clearance_hole", fastener="M7", x=40, y=50))
        res = validate(generate(part))
        self.assertTrue(any(f.level == "error" and f.feature_id == "C9" for f in res.findings))


class TestValidation(unittest.TestCase):
    def test_clean_plate_passes(self):
        res = validate(generate(plate()))
        self.assertEqual(res.findings, [])

    def test_missing_mating_face_is_error(self):
        part = plate()
        part.features = [f for f in part.features if f.id != "F1"]
        res = validate(generate(part))
        self.assertTrue(any(f.level == "error" and "datum A" in f.message for f in res.findings))
        self.assertFalse(res.to_dict()["validation"]["passed"])

    def test_edge_distance_warning(self):
        part = plate()
        part.features.append(Feature("C9", "clearance_hole", fastener="M6", x=5, y=50))
        res = validate(generate(part))
        self.assertTrue(any(f.feature_id == "C9" and "Edge distance" in f.message for f in res.findings))

    def test_hole_outside_outline_is_error(self):
        part = plate()
        part.features.append(Feature("C9", "clearance_hole", fastener="M6", x=170, y=50))
        res = validate(generate(part))
        self.assertTrue(any(f.level == "error" and f.feature_id == "C9" for f in res.findings))

    def test_thin_wall_between_holes(self):
        part = plate()
        part.features.append(Feature("C9", "clearance_hole", fastener="M6", x=22, y=15))
        res = validate(generate(part))
        self.assertTrue(any("Wall between" in f.message for f in res.findings))

    def test_bracket_warns_about_missing_datum_c(self):
        res = validate(generate(Part.from_json(ROOT / "samples" / "sensor_bracket.json")))
        self.assertTrue(any("datum C" in f.message for f in res.findings))


class TestOutput(unittest.TestCase):
    def test_json_is_serialisable_and_complete(self):
        data = json.loads(json.dumps(validate(generate(plate())).to_dict()))
        self.assertEqual(data["schema"], "pmi-assistant/1.0")
        self.assertEqual(data["datum_reference_frame"], ["A", "B", "C"])
        self.assertEqual(len(data["features"]), 9)
        self.assertTrue(data["validation"]["passed"])
        self.assertIn("Datums: A = F1", data["agent_summary"])


if __name__ == "__main__":
    unittest.main()
