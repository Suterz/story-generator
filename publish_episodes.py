"""Publish a hash-bound long-form review package after independent acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(file):
    with file.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def fetch(host, remote, local):
    subprocess.run(["scp", "-q", f"{host}:{remote}", str(local)], check=True, timeout=180)


def write(path, value):
    temporary = path.with_suffix(".new")
    temporary.write_text(value)
    temporary.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("gallery", type=Path)
    p.add_argument("remote")
    p.add_argument("--host", default="zelio-suter@zelio-server")
    p.add_argument("--flagships-only", action="store_true")
    a = p.parse_args()
    watch = a.gallery / "Watch first"
    stage = a.gallery / "Evidence" / "Accepted candidate"
    stage.mkdir(parents=True, exist_ok=True)
    watch.mkdir(parents=True, exist_ok=True)
    slots = [f"{i:02d}" for i in range(1, 4 if a.flagships_only else 11)]
    fetch(a.host, f"{a.remote}/freeze.json", stage / "freeze.json")
    freeze = sha(stage / "freeze.json")
    records = {}
    for slot in slots:
        here = stage / slot
        here.mkdir(exist_ok=True)
        for name in ("episode.json", "outcome.json", "independent-judgment.json", "decoded-review.json"):
            fetch(a.host, f"{a.remote}/{slot}/{name}", here / name)
        judgment = json.loads((here / "independent-judgment.json").read_text())
        video = json.loads((here / "decoded-review.json").read_text())
        receipt = json.loads((here / "outcome.json").read_text())
        if (judgment["verdict"] != "verified_pass" or judgment["freeze_sha256"] != freeze
                or judgment["sha256"] != video["video_sha256"] or judgment["sha256"] != receipt["download_sha256"]):
            raise ValueError(f"{slot} has no verified pass on this freeze")
        if not (180 if slot < "04" else 120) <= video["duration"] <= 300:
            raise ValueError(f"{slot} is outside its required length")
        clip = here / f"{slot}.mp4"
        if not clip.exists():
            incoming = clip.with_suffix(".incoming")
            fetch(a.host, f"{a.remote}/{slot}/video.mp4", incoming)
            if sha(incoming) != judgment["sha256"]:
                raise ValueError(f"{slot} has a mismatched copy")
            subprocess.run(["gst-launch-1.0", "-q", "playbin", f"uri={incoming.resolve().as_uri()}",
                            "audio-sink=fakesink sync=false", "video-sink=fakesink sync=false"],
                           check=True, timeout=300, stdin=subprocess.DEVNULL)
            incoming.replace(clip)
        if sha(clip) != judgment["sha256"]:
            raise ValueError(f"{slot} has a mismatched staged copy")
        records[slot] = (video, judgment)
    # The entire requested set has passed before any public watch file moves.
    playlist = ["#EXTM3U"]
    key = ["# Long Form — Review key", "", f"Candidate SHA-256: `{freeze}`", ""]
    for slot, (video, verdict) in records.items():
        title = json.loads((stage / slot / "episode.json").read_text())["brief"]["topic"]
        final = watch / f"{slot}.mp4"
        if final.exists():
            if sha(final) != verdict["sha256"]:
                raise ValueError(f"Preserve the previous published set before replacing {final}")
        else:
            subprocess.run(["cp", "--reflink=auto", str(stage / slot / final.name), str(final)], check=True)
            if sha(final) != verdict["sha256"]:
                raise ValueError(f"{slot} differs after publishing")
        playlist += [f"#EXTINF:{video['duration']:.3f},{slot}", final.name]
        key += [f"## {slot} — {title}", "",
                f"{video['duration']:.2f} s. **Revisit {verdict['revisit']}.** {verdict['note']}",
                f"First outcome: {verdict['first_outcome']}. Automatic repairs: {verdict['repair_count']}.",
                f"Evidence: {verdict['modality']}.", ""]
    write(watch / "Playlist.m3u", "\n".join(playlist)+"\n")
    write(a.gallery / "Review key.md", "\n".join(key)+"\n")


if __name__ == "__main__":
    main()
