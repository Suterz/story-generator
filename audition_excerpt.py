"""Retimed, same-recording pace auditions; never feed these into a qualification run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def word_count(lines):
    text = " ".join(line["text"] for line in lines).casefold()
    speech = {"$100,000":"one hundred thousand dollars", "gpt-3.5":"g p t three point five",
              "gpt-4":"g p t four", "55%":"fifty five percent", "18%":"eighteen percent"}
    for written, spoken in speech.items():
        text = text.replace(written, spoken)
    return len(re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", text))


def measured(ffmpeg, ffprobe, path, words):
    length = float(subprocess.check_output([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                            "-of", "csv=p=0", str(path)]))
    process = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path), "-vn", "-af",
                              "silencedetect=noise=-35dB:d=0.18", "-f", "null", "-"],
                             check=True, capture_output=True, text=True)
    gaps = sum(float(v) for v in re.findall(r"silence_duration: ([\d.]+)", process.stderr))
    return {"duration": length, "elapsed_wpm": round(60 * words / length, 1),
            "voiced_wpm_proxy": round(60 * words / (length - gaps), 1)}


def generate(media, source, dest):
    ffmpeg, ffprobe = (str(media / p) for p in ("ffmpeg", "ffprobe"))
    clip = source / "video.mp4"
    words = word_count(json.loads((source / "story.json").read_text())["script"])
    baseline = measured(ffmpeg, ffprobe, clip, words)
    dest.mkdir(parents=True, exist_ok=True)
    result = {"source_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(), "words": words, "source": baseline,
              "method": "Identical voice and words, uniform pitch-preserving retime; voiced rate is a proxy excluding "
                        "gaps >=0.18 s below -35 dBFS. All holds are scaled with the timeline.", "variants": {}}
    for target in (165, 185, 200):
        factor = target * baseline["duration"] / (60 * words)
        path = dest / f"{target}.mp4"
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(clip), "-vf",
                        f"setpts=PTS/{factor:.8f},scale=360:640", "-af", f"atempo={factor:.8f}",
                        "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(path)],
                       check=True, timeout=120)
        result["variants"][target] = measured(ffmpeg, ffprobe, path, words)
    (dest / "measurement.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("media", type=Path)
    p.add_argument("source", type=Path)
    p.add_argument("dest", type=Path)
    a = p.parse_args()
    generate(a.media, a.source, a.dest)
