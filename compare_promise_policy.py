"""Development-only counterfactual: adjudicate immutable MP4 packets under two rules."""
import argparse
import hashlib
from pathlib import Path

from daily import ask
from daily_evidence import digest, persist
from opening_review import REVIEWERS, VERDICT
from storygen import ROOT, read, writer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("attempts", nargs="+", type=Path)
    home = Path.home()
    base = home / "ai/storyboard-rehearsal/writer"
    parser.add_argument("--models", type=Path, default=base / "models")
    parser.add_argument("--runtime", type=Path, default=base / "runtime/build/bin/llama-server")
    parser.add_argument("--lease", type=Path, default=home / "ai/storyboard-build/v2/gpu.lock")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    model = read(ROOT / "models.json")["mistral-small"]
    results = {}
    with writer(args, args.models / model["file"], args.output / "reviewer.log") as endpoint:
        for directory in args.attempts:
            label = directory.parent.name if directory.name.startswith("attempt-") else directory.name
            if label in results:
                raise ValueError(f"duplicate replay case label: {label}")
            packet = read(directory / "opening-review-packet.json")
            clip = hashlib.sha256((directory / "video.mp4").read_bytes()).hexdigest()
            if clip != packet["mp4_sha256"]:
                raise ValueError(f"{label}: immutable review packet does not match the MP4")
            row = {"mp4_sha256": clip, "packet_sha256": digest(packet)}
            for version in ("focus-is-relation-v5", "promise-by-question-v6"):
                row[version] = ask(endpoint, REVIEWERS[version], packet, VERDICT, 620,
                                   args.output / f"{label}-{version}-response.json")
            results[label] = row
            persist(args.output / "results.json", results)


if __name__ == "__main__":
    main()
