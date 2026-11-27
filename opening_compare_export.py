"""Compare editorial instructions on the same immutable delivered-opening packet."""
import argparse
import hashlib
from pathlib import Path

from daily import ask
from daily_evidence import digest, persist
from opening_review import REVIEWERS, VERDICT
from storygen import ROOT, read, writer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("output", type=Path)
    home = Path.home()
    base = home / "ai/storyboard-rehearsal/writer"
    parser.add_argument("--models", type=Path, default=base / "models")
    parser.add_argument("--runtime", type=Path, default=base / "runtime/build/bin/llama-server")
    parser.add_argument("--lease", type=Path, default=home / "ai/storyboard-build/v2/gpu.lock")
    args = parser.parse_args()
    packet = read(args.attempt / "opening-review-packet.json")
    clip = hashlib.sha256((args.attempt / "video.mp4").read_bytes()).hexdigest()
    if clip != packet["mp4_sha256"]:
        raise ValueError("observation packet is for a different exported MP4")
    model = read(ROOT / "models.json")["mistral-small"]
    args.output.mkdir(parents=True, exist_ok=False)
    with writer(args, args.models / model["file"], args.output / "reviewer.log") as endpoint:
        for name, instruction in REVIEWERS.items():
            result = ask(endpoint, instruction, packet, VERDICT, 620, args.output / f"{name}-response.json")
            persist(args.output / f"{name}.json", {**result, "mp4_sha256": clip, "packet_sha256": digest(packet)})


if __name__ == "__main__":
    main()
