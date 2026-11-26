"""Assemble an exact repeated-reading control when whole-track ASR collapses repetitions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import wave

import httpx
from video_renderer.api import caption
from video_renderer.media import encode
from video_renderer.timeline import end_frame, start_frame

from morning_art import pause


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def verified_panel(client, folder, session_id, panel, index, parent):
    receipt = folder / f"panel-{index}.json"
    request = {**panel, "key": f"reading-{index}"}
    if parent:
        request["parent_panel_id"] = parent
    if receipt.exists():
        result = read(receipt)
    else:
        response = client.post(f"/v2/sessions/{session_id}/panels", json=request)
        response.raise_for_status()
        result = response.json()
        save(receipt, result)
    deadline = time.monotonic() + 120
    while True:
        response = client.get(result["status_url"])
        response.raise_for_status()
        result = response.json()
        if result["state"] == "accepted":
            break
        if time.monotonic() >= deadline or result["state"] not in ("queued", "running"):
            raise ValueError(f"controlled frame was not accepted: {result}")
        time.sleep(1)
    save(receipt, result)
    image = client.get(result["artifacts"]["composed.png"])
    image.raise_for_status()
    return result["panel_id"], image.content


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path)
    p.add_argument("frames_url")
    p.add_argument("toolroot", type=Path)
    p.add_argument("worker", type=Path)
    a = p.parse_args()
    out = a.out
    if (out / "outcome.json").exists():
        return
    proof = read(out / "pause-proof.json")
    raw = out / "single.wav"
    with wave.open(str(raw), "rb") as handle:
        assert (handle.getnchannels(), handle.getsampwidth(), handle.getframerate()) == (1, 2, 48000)
        original = handle.readframes(handle.getnframes())
    assert hashlib.sha256(original).hexdigest() == proof["repeated_pcm_sha256"]
    source_words = subprocess.check_output(
        [str(a.toolroot / "venvs/v2-asr/bin/python"), "-B", str(a.worker),
         "asr", str(a.toolroot / "speech"), str(raw)], input=b"{}", timeout=120)
    words = json.loads(source_words.splitlines()[-1])
    if [re.sub(r"\W+", "", w["word"]).casefold() for w in words] != ["the", "door", "opened", "slowly"]:
        raise ValueError("single copied recording did not pass independent word recognition")
    split = proof["split_sample"]
    delay = proof["second_pass_inserted_silence_ms"] * 48
    second = len(original) // 2 + 48000
    audio = out / "exact-repeat.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        handle.writeframes(original + bytes(96000) + original[:split * 2] + bytes(delay * 2) + original[split * 2:])
    story = pause()
    save(out / "story.json", story)
    frames = []
    with httpx.Client(base_url=a.frames_url, timeout=30) as client:
        receipt = out / "frame-session.json"
        if not receipt.exists():
            response = client.post("/v2/sessions", json=story["visual"])
            response.raise_for_status()
            save(receipt, response.json())
        session_id = read(receipt)["session_id"]
        parent = None
        for i, beat in enumerate(story["beats"]):
            parent, data = verified_panel(client, out, session_id, beat["panel"], i, parent)
            frame = out / f"reading-{i}.png"
            frame.write_bytes(data)
            frames.append(frame)
    second_frame = start_frame(second, 30)
    slowly_frame = start_frame(second + split + delay, 30)
    paths = [out / f"caption-{i}.png" for i in range(3)]
    captions = ["The door opened slowly.", "The door opened…", "Slowly."]
    for i, path in enumerate(paths):
        caption(frames[min(i, 1)], path, captions[i], 51)
    stop = end_frame(second + len(original) // 2 + delay, 30)
    boundaries = [0, second_frame, slowly_frame, stop]
    segments = [(lo, hi, i) for i, (lo, hi) in enumerate(zip(boundaries, boundaries[1:]))]
    clip = out / "video.mp4"
    verification = encode(paths, segments, (1080, 1920), 30, stop, audio, clip)
    save(out / "manifest.json", {"verification": verification,
         "beats": [{"frame": frame} for frame in boundaries[:-1]], "asr": words,
         "asr_modality": "One source recording transcribed independently; the same PCM repeated with authored silence",
         "caption_trace": [{"start_frame": lo, "end_frame": hi, "text": captions[i]} for lo, hi, i in segments],
         "second_reading_start_sample": second, "pause_start_sample": second + split})
    save(out / "outcome.json", {"state": "succeeded",
         "method": "accepted frames and local video-worker encoder; agent-assisted",
         "download_sha256": hashlib.sha256(clip.read_bytes()).hexdigest()})


if __name__ == "__main__":
    main()
