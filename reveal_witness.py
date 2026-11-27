"""Measure the first spoken reveal against the simultaneous diagram."""
import argparse
import fcntl
import hashlib
from pathlib import Path
import re
import subprocess

from daily_evidence import persist
from review_daily import worker
from storygen import read


def expectation(packet):
    match = re.search(r"\b(?:must not|should not) reveal (\$\d+(?:\.\d+)?)\b", packet["objective"], re.I)
    if match and re.search(r"later yields " + re.escape(match[1]) + r"\b", packet["evidence"], re.I):
        return match[1]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("packets", "observations", "output", "frames"):
        parser.add_argument(key, type=Path)
    args = parser.parse_args()
    home = Path.home()
    fresh = home / "ai/storyboard-rehearsal/fresh"
    ffmpeg = home / "ai/tools/media/bin/ffmpeg"
    specs, jobs = {}, []
    args.output.mkdir(exist_ok=False)
    for case in sorted(args.packets.iterdir()):
        packet = read(case / "packet.json")
        if target := expectation(packet):
            specs[case.name] = {"answer": target, "mp4_sha256": packet["mp4_sha256"]}
    persist(args.output / "expected-before-observation.json", specs)
    for name, row in specs.items():
        clip = args.packets / name / "video.mp4"
        if hashlib.sha256(clip.read_bytes()).hexdigest() != row["mp4_sha256"]:
            raise ValueError(f"{name}: immutable MP4 changed")
        threshold = re.escape(row["answer"].removeprefix("$"))
        words = read(args.observations / name / "actual-words.json")
        first = next((w for w in words if re.fullmatch(r"\$?" + threshold + r"[.,!]?", w["word"].strip())), None)
        if first is None:
            continue
        image = args.output / f"{name}.png"
        subprocess.run([str(ffmpeg), "-v", "error", "-ss", str(first["start"]), "-i", str(clip),
                        "-frames:v", "1", "-vf", "scale=360:640,crop=360:520:0:0", str(image)], check=True, timeout=60)
        jobs.append((name, image, first))
    # Use the same vision weights, but constrain attention to physical panel text.
    with (home / "ai/storyboard-build/v2/gpu.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        observations = worker([fresh / "venvs/storyboard-vision/bin/python",
                               args.frames / "src/storyboard_renderer/multi_review.py"],
                              [{"images": [["Phone frame at first mention", str(image)]],
                                "prompt": "Copy all dollar amounts visibly printed in this diagram. "
                                          "Do not infer missing prices or perform calculations."}
                               for _, image, _ in jobs])
    results = {}
    for (name, _, word), text in zip(jobs, observations, strict=True):
        expected = specs[name]
        present = expected["answer"] in text
        results[name] = {**expected, "first_spoken_seconds": word["start"],
                         "printed_diagram_observation": text, "seen_at_first_mention": present}
    persist(args.output / "results.json", results)


if __name__ == "__main__":
    main()
