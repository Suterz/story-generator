"""Summarize script and actual video verdicts without treating exports as passes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from storygen import read
from review_packets import first_script


def verdict_for(record_path, artifact, field):
    record = read(record_path)
    with artifact.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    if record[field] != digest:
        raise ValueError(f"{record_path}: judgment does not bind to the reviewed artifact")
    return record["verdict"]


def score(run):
    scripts, drafts, videos = Counter(), Counter(), Counter()
    cases = {}
    total = read(run / "freeze.json")["case_ids"]
    for case in total:
        folder = run / case
        editorial = folder / "script-judgment.json"
        first_editorial = folder / "first-script-judgment.json"
        first_attempt = folder / "writer-attempt-0.json"
        draft_state = (verdict_for(first_editorial, first_attempt, "first_attempt_sha256")
                       if first_editorial.exists() else
                       "unjudged" if first_script(first_attempt) is not None else "no_script")
        drafts[draft_state] += 1
        script_state = verdict_for(editorial, folder / "story.json", "story_file_sha256") if editorial.exists() else (
            "unjudged" if (folder / "story.json").exists() else "no_script")
        scripts[script_state] += 1
        outcome = folder / "outcome.json"
        if outcome.exists():
            status = read(outcome)
            if status["state"] == "succeeded":
                videos["returned"] += 1
                verdict = folder / "video-judgment.json"
                if verdict.exists():
                    record = read(verdict)
                    with (folder / "video.mp4").open("rb") as f:
                        digest = hashlib.file_digest(f, "sha256").hexdigest()
                    if record["sha256"] != status["download_sha256"] or record["sha256"] != digest:
                        raise ValueError(f"{case}: verdict does not bind to the returned video")
                    video_state = record["verdict"]
                    if video_state not in ("verified_pass", "incorrect_accepted"):
                        raise ValueError(f"{case}: unrecognized independent verdict")
                    if video_state == "verified_pass":
                        manifest = read(folder / "manifest.json")
                        repairs = [panel.get("accepted_attempt") for panel in manifest["panels"]]
                        if any(attempt is None for attempt in repairs):
                            repair = "repair_count_unknown"
                        elif any(repairs) or (folder / "writer-attempt-1.json").exists():
                            repair = "repaired_pass"
                        else:
                            repair = "first_candidate_pass"
                        videos[repair] += 1
                else:
                    video_state = "unjudged"
                if read(folder / "manifest.json")["verification"]["expected_duration"] < 30:
                    videos["under_30_seconds"] += 1
            else:
                video_state = "renderer_refusal" if status["state"] == "needs_review" else "operational_failure"
        elif (folder / "result.json").exists():
            video_state = read(folder / "result.json")["status"]
        elif (folder / "writer-refusal.json").exists():
            video_state = "writer_refusal"
        elif (folder / "run.log").exists() and "Traceback" in (folder / "run.log").read_text():
            video_state = "operational_failure"
        else:
            video_state = "pending"
        videos[video_state] += 1
        cases[case] = {"first_script": draft_state, "script": script_state, "video": video_state}
    return {"planned": len(total), "first_script": dict(drafts), "script": dict(scripts),
            "video": dict(videos), "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    print(json.dumps(score(parser.parse_args().run), indent=2))
