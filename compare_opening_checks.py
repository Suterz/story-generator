"""Compare a checklist with the open-ended reviewer on immutable development packets."""
import argparse
import hashlib
from pathlib import Path

from daily import TEXT, ask, obj
from daily_evidence import digest, persist
from opening_review import REVIEWERS, VERDICT
from storygen import ROOT, read, writer

CHECK = obj({"answer": {"enum": ["yes", "no", "uncertain"]}, "observation": {**TEXT, "maxLength": 250}})
QUESTIONS = {
    "orient": "Does the first line direct attention to its visible evidence? Use the decoded focus mark when present.",
    "promise": "Is there a heard question or promise that matches the teaching objective by the end?",
    "unresolved": "Is the requested comparison kept unresolved until the promised evidence, rather than stating the winner?",
    "faithful": "Do the numbers and units actually heard match the appropriate object in the same visible interval and source?",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("attempts", type=Path, nargs="+")
    base = Path.home() / "ai/storyboard-rehearsal/writer"
    parser.add_argument("--models", type=Path, default=base / "models")
    parser.add_argument("--runtime", type=Path, default=base / "runtime/build/bin/llama-server")
    parser.add_argument("--lease", type=Path, default=Path.home() / "ai/storyboard-build/v2/gpu.lock")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = read(ROOT / "models.json")["mistral-small"]
    with writer(args, args.models / config["file"], args.output / "reviewer.log") as endpoint:
        for directory in args.attempts:
            name = directory.parent.name if directory.name.startswith("attempt-") else directory.name
            packet = read(directory / "opening-review-packet.json")
            mp4 = hashlib.sha256((directory / "video.mp4").read_bytes()).hexdigest()
            if mp4 != packet["mp4_sha256"]:
                raise ValueError(f"{name}: observation packet does not bind to delivered clip")
            try:
                before = ask(endpoint, REVIEWERS["focus-is-relation-v5"], packet, VERDICT, 620,
                             args.output / f"{name}-baseline-response.json")
            except ValueError as error:
                before = {"status": "uncertain", "detail": str(error)}
            checks = {}
            for key, question in QUESTIONS.items():
                try:
                    checks[key] = ask(endpoint, "Answer this one check from delivered evidence only. Cite time and "
                                      "the sound or pixels. If missing, use uncertain. " + question,
                                      packet, CHECK, 240, args.output / f"{name}-{key}-response.json")
                except ValueError as error:
                    checks[key] = {"answer": "uncertain", "observation": str(error)}
            passing = all(row["answer"] == "yes" for row in checks.values())
            persist(args.output / f"{name}-comparison.json", {"mp4_sha256": mp4, "packet_sha256": digest(packet),
                    "baseline_status": before["status"], "checklist_diagnostic": "pass" if passing else "hold",
                    "checks": checks})


if __name__ == "__main__":
    main()
