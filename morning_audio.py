"""Collect independent transcript evidence from the delivered MP4, not a source WAV."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("toolroot", type=Path)
    p.add_argument("video_repo", type=Path)
    a = p.parse_args()
    worker = a.video_repo / "src/video_renderer/speech_worker.py"
    ffmpeg = a.toolroot / "media/bin/ffmpeg"
    env = {**os.environ, "STORY_FFMPEG": str(ffmpeg), "HF_HUB_OFFLINE": "1"}
    for arm in ("first", "assisted", "assisted-refined"):
        for status_file in sorted((a.root / arm).glob("*/outcome.json")):
            folder = status_file.parent
            status = json.loads(status_file.read_text())
            if status["state"] != "succeeded":
                continue
            clip = folder / "video.mp4"
            transcript = folder / "mux-speech.json"
            if transcript.exists():
                continue
            with clip.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            if status["download_sha256"] != digest:
                raise ValueError(f"{clip}: exported clip does not match its receipt")
            result = subprocess.check_output(
                [str(a.toolroot / "venvs/v2-asr/bin/python"), "-B", str(worker),
                 "asr", str(a.toolroot / "speech"), str(clip)],
                input=b"{}", env=env, timeout=120)
            words = json.loads(result.splitlines()[-1])
            review = {"mp4_sha256": digest, "modality": "ASR on decoded MP4 audio track; no listening",
                      "words": words}
            temporary = transcript.with_suffix(".tmp")
            temporary.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
            temporary.replace(transcript)
            print(arm, folder.name, " ".join(w["word"].strip() for w in words), flush=True)


if __name__ == "__main__":
    main()
