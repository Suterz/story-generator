"""Report independent accepted-video verdicts without treating export as success."""
import argparse
from collections import Counter
import json
from pathlib import Path

from storygen import read


VERDICTS = {"verified_pass", "incorrect_accepted"}
CHECKS = ("facts", "phone", "continuity", "prediction", "reveal", "speech", "decode")


def score(root):
    counts = Counter()
    rows = []
    for key in read(root / "freeze.json")["case_ids"]:
        folder = root / key
        first = folder / "outcome.json"
        verdict_path = folder / "independent.json"
        run_log = folder / "run.log"
        if first.is_file():
            outcome = read(first)
            if outcome["state"] == "succeeded":
                counts["returned"] += 1
                if not verdict_path.is_file():
                    state = "unjudged"
                else:
                    verdict = read(verdict_path)
                    assert verdict["media_sha256"] == outcome["download_sha256"]
                    state = verdict["verdict"]
                    assert state in VERDICTS and all(verdict.get(c) for c in CHECKS)
                    if state == "verified_pass":
                        writer_repaired = (folder / "writer-attempt-1.json").is_file()
                        frame_repair_count = verdict["frame_repairs"]
                        assert isinstance(frame_repair_count, int) and frame_repair_count >= 0
                        counts["repair_pass" if writer_repaired or frame_repair_count else "first_candidate"] += 1
            elif outcome["state"] == "needs_review":
                state = "withheld"
            else:
                state = "operational_failure"
        elif (folder / "writer-refusal.json").is_file():
            state = "writer_refusal"
        elif run_log.is_file() and "Traceback (most recent call last)" in run_log.read_text():
            state = "operational_failure"
        else:
            state = "pending"
        rows.append({"case": key, "outcome": state})
        counts[state] += 1
    return {"planned": len(rows), "counts": dict(counts), "cases": rows}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    print(json.dumps(score(p.parse_args().root), indent=2))
