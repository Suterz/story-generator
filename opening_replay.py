"""Compare versioned judges on identical frozen observations from exported media."""
import argparse
import hashlib
import json
from pathlib import Path

from daily import ask
from daily_evidence import digest, persist
from opening_review import REVIEWERS, VERDICT
from review_daily import editorial
from storygen import ROOT, read, writer


def run(args):
    model = read(ROOT / "models.json")["mistral-small"]
    inputs = []
    for directory in sorted(args.packets.iterdir()):
        source = read(directory / "packet.json")
        clip = directory / "video.mp4"
        actual = hashlib.sha256(clip.read_bytes()).hexdigest()
        if actual != source["mp4_sha256"]:
            raise ValueError(f"{directory.name}: changed exported clip")
        observed = read(args.observations / directory.name / "observations.json")
        packet = {"objective": source["objective"], "evidence": source["evidence"], "delivered": observed}
        inputs.append((directory.name, actual, packet))
    args.output.mkdir(parents=True, exist_ok=False)
    with writer(args, args.models / model["file"], args.output / "model.log") as endpoint:
        for case, clip, packet in inputs:
            target = args.output / case
            target.mkdir()
            for version in ("chapter-editorial-v1", *REVIEWERS):
                try:
                    if version == "chapter-editorial-v1":
                        result = editorial(endpoint, packet)
                    else:
                        result = ask(endpoint, REVIEWERS[version], packet, VERDICT, 620, target / f"{version}-response.json")
                except ValueError as error:
                    result = {"status": "uncertain", "code": "unobservable", "detail": str(error), "start_seconds": 0}
                persist(target / f"{version}.json", {**result, "mp4_sha256": clip,
                        "observation_sha256": digest(packet), "reviewer_sha256": model["sha256"], "version": version})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packets", "observations", "output"):
        parser.add_argument(name, type=Path)
    prefix = Path.home() / "ai/storyboard-rehearsal/writer"
    parser.add_argument("--models", type=Path, default=prefix / "models")
    parser.add_argument("--runtime", type=Path, default=prefix / "runtime/build/bin/llama-server")
    parser.add_argument("--lease", type=Path, default=Path.home() / "ai/storyboard-build/v2/gpu.lock")
    run(parser.parse_args())
