"""Commit a custodian's independent labels without copying them to reviewer input."""
import argparse
import hashlib
import json
from pathlib import Path


def bytes_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packets", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rubric", required=True)
    parser.add_argument("--configuration", required=True, type=Path,
                        help="frozen candidate and reviewer configuration receipt")
    parser.add_argument("--tolerance", type=float, default=.75)
    args = parser.parse_args()
    labels = json.loads(args.labels.read_text())
    if len(labels) != 24 or sum(row["quality"] == "good" for row in labels.values()) != 12 \
            or sum(row["quality"] == "bad" for row in labels.values()) != 12:
        raise ValueError("use exactly 12 independently good and 12 independently bad cases")
    clips = {}
    for key, row in labels.items():
        if not key or Path(key).name != key or key in {".", ".."}:
            raise ValueError("invalid opaque case identifier")
        interval = row.get("interval_seconds")
        if not row.get("reason") or (row["quality"] == "bad" and
                (not row.get("defect") or type(row.get("critical")) is not bool
                 or not isinstance(interval, list) or len(interval) != 2
                 or any(type(t) not in (int, float) for t in interval)
                 or not 0 <= interval[0] <= interval[1])):
            raise ValueError(f"{key}: label needs a reason and bad clips need a defect and observed interval")
        clips[key] = bytes_sha(args.packets / key / "video.mp4")
    with args.output.open("x") as file:
        json.dump({"labels_sha256": bytes_sha(args.labels), "rubric": args.rubric,
                   "configuration_sha256": bytes_sha(args.configuration),
                   "timing_tolerance_seconds": args.tolerance, "clips": clips}, file, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
