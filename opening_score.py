"""Score sealed opening judgments separately from the generation/review process."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(seal, labels, results, qualification=False):
    lock = read(seal)
    truth = read(labels)
    if lock["labels_sha256"] != sha(labels) or set(lock["clips"]) != set(truth):
        raise ValueError("reveal key does not match the predeclared seal")
    counts = {"bad": 0, "good": 0, "bad_accepted": 0, "good_withheld": 0,
              "correctly_localized": 0, "incorrect_diagnosis_on_withholds": 0}
    details = {}
    tolerance = lock["timing_tolerance_seconds"]
    for case, label in truth.items():
        if not case or case != Path(case).name or case in {".", ".."}:
            raise ValueError(f"invalid case id: {case!r}")
        if label["quality"] not in ("good", "bad"):
            raise ValueError("expected good/bad independent labels")
        prediction = read(results / case / "local-opening-verdict.json")
        if prediction["mp4_sha256"] != lock["clips"][case]:
            raise ValueError(f"{case}: judgment belongs to different media")
        if prediction["status"] not in ("accepted", "failed", "uncertain"):
            raise ValueError(f"{case}: invalid reviewer verdict")
        quality = label["quality"]
        accepted = prediction["status"] == "accepted"
        counts[quality] += 1
        counts["bad_accepted"] += quality == "bad" and accepted
        counts["good_withheld"] += quality == "good" and not accepted
        localized = False
        if quality == "bad" and not accepted:
            moment = prediction["start_seconds"]
            start, end = label["interval_seconds"]
            localized = prediction["code"] == label["defect"] and start-tolerance <= moment <= end+tolerance
            counts["correctly_localized"] += localized
            counts["incorrect_diagnosis_on_withholds"] += not localized
        details[case] = {"label": label, "prediction": prediction, "localized": localized}
    if qualification and (counts["bad"] != 12 or counts["good"] != 12):
        raise ValueError("qualification requires 12 bad and 12 good cases")
    counts["gate_passed"] = bool(qualification and counts["bad_accepted"] == 0 and counts["good_withheld"] <= 1)
    return {"counts": counts, "details": details, "rubric": lock["rubric"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for item in ("seal", "labels", "results"):
        parser.add_argument(item, type=Path)
    parser.add_argument("--qualification", action="store_true")
    args = parser.parse_args()
    print(json.dumps(score(args.seal, args.labels, args.results, args.qualification), indent=2))
