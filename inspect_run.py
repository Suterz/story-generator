"""Extract actual decoded phone frames for independent lesson review."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from storygen import read, save


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--ffmpeg", required=True)
    p.add_argument("--ffprobe", required=True)
    a = p.parse_args()
    cases = read(a.root / "freeze.json")["case_ids"]
    summary = []
    for key in cases:
        folder = a.root / key
        status = folder / "outcome.json"
        if not status.exists():
            state = "writer_refusal" if (folder / "writer-refusal.json").is_file() else "pending_or_interrupted"
            summary.append({"case": key, "state": state})
            continue
        result = read(status)
        if result["state"] != "succeeded":
            summary.append({"case": key, "state": result["state"], "diagnostic": result.get("error")})
            continue
        media = folder / "video.mp4"
        digest = hashlib.sha256(media.read_bytes()).hexdigest()
        if result["download_sha256"] != digest:
            raise ValueError(f"{key} MP4 hash disagrees with its receipt")
        probe = json.loads(subprocess.check_output([a.ffprobe, "-v", "error", "-count_frames", "-show_streams",
                                                   "-show_format", "-of", "json", str(media)]))
        v = next(s for s in probe["streams"] if s["codec_type"] == "video")
        audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        duration = float(probe["format"]["duration"])
        assert max(duration, float(v["duration"]), float(audio["duration"])) < 45
        assert (v["codec_name"], audio["codec_name"]) == ("h264", "aac")
        assert v["width"] * 16 == v["height"] * 9
        manifest = read(folder / "manifest.json")
        last = int(v["nb_read_frames"]) - 1
        frames = {0, last}
        for b in manifest["beats"][1:]:
            frames.update({b["frame"] - 1, b["frame"]})
        for cap in manifest["caption_trace"]:
            if cap["text"]:
                frames.add(cap["start_frame"])
        frames = sorted(frames)
        selection = "+".join(f"eq(n\\,{n})" for n in frames)
        dest = folder / "decoded"
        dest.mkdir(exist_ok=True)
        subprocess.run([a.ffmpeg, "-v", "error", "-y", "-i", str(media), "-an", "-vf",
                        f"select={selection},scale=360:640", "-fps_mode", "passthrough",
                        str(dest / "sample-%03d.png")], check=True, timeout=120)
        assert len(list(dest.glob("sample-*.png"))) == len(frames)
        summary.append({"case": key, "state": "ready_for_review", "duration": duration, "frames": frames,
                        "mp4_sha256": digest, "evidence": str(dest), "adjudication": "unjudged"})
    save(a.root / "review-index.json", summary)


if __name__ == "__main__":
    main()
