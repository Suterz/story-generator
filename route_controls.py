"""Development route probes; their labels never enter the model input."""
import argparse
from pathlib import Path

from daily import TEXT, ask, obj
from daily_evidence import persist
from storygen import ROOT, read, writer

CASES = [
    ("same-lens-proof", "Show that a unit square and a 90-degree view of it have different projected widths.",
     "Use an orthographic projection. Face-on width is one unit; edge-on width is zero. "
     "The same four points make the square in both views.", "exact", False),
    ("same-lens-document", "Show the authentic 1990 Hubble deployment photograph and identify the telescope in it.",
     "The caller established when and by whom the telescope was deployed.", "authentic", False),
    ("same-lens-decoration", "Use a whimsical telescope illustration while asking viewers about their favorite night sky.",
     "No documentary claim. Any clearly recognizable telescope works.", "illustration", False),
    ("pollen-gap", "Compare published pollen counts for the same city in two named years using a chart.",
     "The caller names the city and years, but has not supplied any counts.", "exact", True),
]
PROMPT = ("Decide separately whether new factual evidence is needed and how to obtain the visual. "
          "Choose exact for a quantitative or controlled relationship, authentic when seeing the actual source "
          "is essential, and illustration when appearance can vary. A documentary asset search is not the "
          "same as a factual source gap. Give one concrete reason.")
CLOSED_PACK = ("Treat the caller's explicit facts and hypothetical assumptions as sufficient for a claim they "
               "already settle. Do not research the visual method, object or technique just to draw it. "
               "Mark research only when a missing factual premise could change the answer.")
SCHEMA = obj({"kind": {"enum": ["exact", "authentic", "illustration"]},
              "needs_fact_research": {"type": "boolean"}, "reason": {**TEXT, "maxLength": 220}})


def main():
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    writer_root = home / "ai/storyboard-rehearsal/writer"
    parser.add_argument("--models", type=Path, default=writer_root / "models")
    parser.add_argument("--runtime", type=Path, default=writer_root / "runtime/build/bin/llama-server")
    parser.add_argument("--lease", type=Path, default=home / "ai/storyboard-build/v2/gpu.lock")
    parser.add_argument("--version", choices=("route-v1", "route-v2"), default="route-v1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    model = read(ROOT / "models.json")["mistral-small"]
    with writer(args, args.models / model["file"], args.output / "writer.log") as endpoint:
        results = []
        for case, objective, evidence, route, needs_research in CASES:
            instructions = PROMPT if args.version == "route-v1" else PROMPT + " " + CLOSED_PACK
            observed = ask(endpoint, instructions, {"objective": objective, "evidence": evidence}, SCHEMA,
                           450, args.output / f"{case}.json")
            results.append({"id": case, "expected_route": route, "expected_research": needs_research,
                            "route_matches": observed["kind"] == route,
                            "research_matches": observed["needs_fact_research"] == needs_research,
                            "observed": observed})
    persist(args.output / "results.json", {"cases": results, "model": model["sha256"], "version": args.version})


if __name__ == "__main__":
    main()
