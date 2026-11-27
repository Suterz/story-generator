"""Report timing and hold evidence without assigning subjective viewer labels."""
import argparse
import hashlib
import json
from pathlib import Path

from opening_review import meter_faults


def read(path):
    return json.loads(path.read_text())


def measure(attempt):
    clip = attempt / "video.mp4"
    decoded = read(attempt / "decoded-review.json")
    manifest = read(attempt / "manifest.json")
    words = read(attempt / "delivered-track.json")["asr"]
    actual = hashlib.sha256(clip.read_bytes()).hexdigest()
    if actual != read(attempt / "outcome.json")["download_sha256"]:
        raise ValueError("review does not bind to downloaded MP4")
    fps = decoded["fps"]
    focus = {}
    faults = meter_faults(attempt, decoded, manifest, words, focus)
    observations = []
    for i, cue in enumerate(decoded["cues"]):
        start = cue["seconds"]
        end = decoded["cues"][i+1]["seconds"] if i+1 < len(decoded["cues"]) else decoded["duration"]
        spoken = [w for w in words if start <= (w["start"]+w["end"])/2 < end]
        observations.append({"cue": cue["id"], "start_seconds": start,
                             "previous_frame": cue["frame"]-1 if cue["frame"] else None,
                             "first_current_frame": cue["frame"],
                             "current_frame_seconds": cue["frame"]/fps, "focus": focus.get(cue["id"]),
                             "spoken": "".join(w["word"] for w in spoken)})
    return {"mp4_sha256": actual, "duration_seconds": decoded["duration"], "observations": observations,
            "faults": faults, "viewer_engagement": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    print(json.dumps(measure(parser.parse_args().attempt), indent=2))
