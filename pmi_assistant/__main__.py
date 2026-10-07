"""Command line: python -m pmi_assistant samples/*.json --out docs"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import Part
from .report import build_page
from .rules import generate
from .validate import validate

REPO_URL = "https://github.com/sajin-saji/pmi-assistant"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Suggest and validate PMI for machined parts.")
    ap.add_argument("parts", nargs="+", help="part feature files (JSON)")
    ap.add_argument("--out", default="docs", help="output folder for JSON and the HTML report")
    ap.add_argument("--strict", action="store_true", help="exit with code 1 if any part has validation errors")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results, failed = [], False
    for path in args.parts:
        res = validate(generate(Part.from_json(path)))
        name = Path(path).stem + ".pmi.json"
        (out / name).write_text(json.dumps(res.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        results.append((res, name))
        errors = [f for f in res.findings if f.level == "error"]
        failed |= bool(errors)
        print(f"{res.part.name}: {len(res.annotations)} annotations, {len(errors)} errors, "
              f"{len(res.findings) - len(errors)} warnings -> {out / name}")
    (out / "index.html").write_text(build_page(results, REPO_URL), encoding="utf-8")
    print(f"Report -> {out / 'index.html'}")
    return 1 if (failed and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
