"""Render the authored contract control, then verify same-art voice reuse."""
import argparse
from pathlib import Path
import subprocess
import sys

from storygen import ROOT, read, save


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--video-url", required=True)
    p.add_argument("--story", type=Path, default=ROOT / "examples/carriage/contract-story.json")
    p.add_argument("--original", type=Path)
    a = p.parse_args()
    project = ROOT / "storygen.py"
    a.out.mkdir(parents=True, exist_ok=True)

    def render(path, folder):
        subprocess.run([sys.executable, "-B", str(project), "render", str(path),
                        "--out", str(folder), "--video-url", a.video_url], check=True)
        return read(folder / "outcome.json")

    original = a.original or a.out / "heart"
    result = read(original / "outcome.json") if a.original else render(a.story, original)
    if result["state"] != "succeeded":
        return
    story = read(a.story)
    story.update(voice_profile="ryan", reuse_visuals_from=result["id"])
    path = a.out / "ryan-story.json"
    save(path, story)
    other = a.out / "ryan"
    assert render(path, other)["state"] == "succeeded"
    before, after = (read(x / "manifest.json") for x in (original, other))
    art = lambda manifest: [panel["sha256"] for panel in manifest["panels"]]
    cuts = lambda manifest: [beat["frame"] for beat in manifest["beats"]]
    assert art(before) == art(after) and after["reused"]
    assert before["wav_sha256"] != after["wav_sha256"]
    assert cuts(before) != cuts(after), "the example must actually show different cut times"
    save(a.out / "voice-reuse.json", {"same_accepted_art": art(before), "heart_cuts": cuts(before),
                                    "ryan_cuts": cuts(after), "new_recording": True})


if __name__ == "__main__":
    main()
