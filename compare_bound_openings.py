"""Matched writer development diagnostic; does not score rendered or viewer outcomes."""
import argparse
import hashlib
from pathlib import Path

from daily_evidence import persist
from opening_bindings import bound_opening
from storygen import ROOT, read, writer


def main():
    base = Path.home() / "ai/storyboard-rehearsal/writer"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("briefs", nargs="+", type=Path)
    parser.add_argument("--models", type=Path, default=base / "models")
    parser.add_argument("--runtime", type=Path, default=base / "runtime/build/bin/llama-server")
    parser.add_argument("--lease", type=Path, default=Path.home() / "ai/storyboard-build/v2/gpu.lock")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    pin = read(ROOT / "models.json")["mistral-small"]
    results = []
    with writer(args, args.models / pin["file"], args.output / "matched-writer.log") as endpoint:
        for brief in args.briefs:
            inputs = read(brief)
            # This isolates the authoring step with identical evidence in both arms.
            approved = {"supplied": {"passages": inputs["facts"]}}
            for version, neutral, menu in (("source-bound-v10", False, False), ("neutral-question-v11", True, False),
                                           ("bound-options-v12", True, True)):
                case = args.output / brief.stem / version
                case.mkdir(parents=True)
                try:
                    plan = bound_opening(endpoint, inputs, approved, case, neutral_question=neutral, menu=menu)
                except ValueError as error:
                    result = {"status": "withheld", "reason": str(error)}
                else:
                    persist(case / "plan.json", plan)
                    result = {"status": "authored", "promise": plan["promise"]}
                results.append({"brief": brief.stem, "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest(),
                                "version": version, **result})
    persist(args.output / "results.json", {"model_sha256": pin["sha256"], "results": results})


if __name__ == "__main__":
    main()
