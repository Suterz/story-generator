"""Read-only review of the actual returned MP4 and cue manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def read(path):
    return json.loads(path.read_text())


def review(folder, ffmpeg, ffprobe):
    clip = folder / "video.mp4"
    manifest = read(folder / "manifest.json")
    digest = hashlib.sha256(clip.read_bytes()).hexdigest()
    receipt = folder / "download-receipt.json"
    if not receipt.is_file():
        receipt = folder / "outcome.json"
    if read(receipt)["download_sha256"] != digest:
        raise ValueError("download differs from the original receipt")
    probe = json.loads(subprocess.check_output(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(clip)]))
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
    if denominator != 1:
        raise ValueError("episode validation expects integer frame rate")
    fps = numerator
    n = manifest["verification"]["expected_video_frames"]
    if int(stream["nb_frames"]) != n:
        raise ValueError("decoded timeline count differs from the manifest")
    subprocess.run([ffmpeg, "-v", "error", "-xerror", "-i", str(clip), "-f", "null", "-"], check=True, timeout=300)
    boundaries = [b["frame"] for b in manifest["beats"]]
    chapter_joins = [(x["start_sample"] * fps + 24000) // 48000
                     for x in manifest.get("speech_groups", [])]
    boundaries += chapter_joins
    frames = sorted({0, n - 1, *boundaries, *(max(0, frame - 1) for frame in boundaries)})
    dest = folder / "phone"
    dest.mkdir(exist_ok=True)
    select = "+".join(f"eq(n\\,{frame})" for frame in frames)
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(clip), "-vf",
                    f"select={select},scale=360:640", "-fps_mode", "passthrough",
                    str(dest / "%03d.png")], check=True, timeout=300)
    if not all((dest / f"{i:03d}.png").exists() for i in range(1, len(frames)+1)):
        raise ValueError("a selected frame could not be decoded")
    result = {"video_sha256": digest, "duration": float(probe["format"]["duration"]),
              "fps": fps, "frames": frames, "chapter_join_frames": chapter_joins,
              "cues": [{"id": b["id"], "frame": b["frame"],
                        "seconds": b["frame"] / fps, "cue": b["cue"]} for b in manifest["beats"]]}
    (folder / "decoded-review.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("--media", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(review(a.folder, str(a.media / "ffmpeg"), str(a.media / "ffprobe")), indent=2))
