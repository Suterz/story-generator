"""Generate local judgments for opaque archive cases, then score in a separate step."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess

from daily_evidence import persist
from review_daily import editorial, worker
from storygen import ROOT, read, writer


def observations(args, case, folder, clip):
    runtime = args.fresh
    audio_worker = args.video / "src/video_renderer/speech_worker.py"
    vision_worker = args.frames / "src/storyboard_renderer/multi_review.py"
    queries, speech = [], []
    for i, window in enumerate(case["windows"]):
        start, end = window["start"], window["end"]
        if not 0 <= start < end <= start + 40:
            raise ValueError("calibration windows must be bounded consecutive excerpts")
        wav = folder / f"{i}.wav"
        frame = folder / f"{i}.png"
        subprocess.run([str(args.ffmpeg), "-v", "error", "-ss", str(start), "-i", str(clip),
                        "-t", str(end-start), "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav)],
                       check=True, timeout=30)
        decoded = worker([runtime / "venvs/v2-asr/bin/python", audio_worker, "asr", runtime / "speech", wav], {})
        speech.append({"timestamp_seconds": start, "end_seconds": end,
                       "spoken_ASR": "".join(row["word"] for row in decoded)})
        subprocess.run([str(args.ffmpeg), "-v", "error", "-ss", str(window["inspect"]), "-i", str(clip),
                        "-frames:v", "1", "-vf", "scale=360:640", str(frame)], check=True, timeout=30)
        queries.append({"images": [["Decoded phone frame", str(frame)]],
                        "prompt": "Describe the visible objects, relations and labels exactly. "
                                  "Include numbers and distinguish uncertainty."})
    with args.lease.open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        seen = worker([runtime / "venvs/storyboard-vision/bin/python", vision_worker], queries)
    for audio, vision, window in zip(speech, seen, case["windows"], strict=True):
        audio.update(observed_pixels=vision, frame_seconds=window["inspect"])
    return speech


def calibrate(args):
    output = args.output
    output.mkdir(exist_ok=False, parents=True)
    observations_by_case = {}
    for folder in sorted(args.packets.iterdir()):
        case = read(folder / "packet.json")
        clip = folder / "video.mp4"
        if hashlib.sha256(clip.read_bytes()).hexdigest() != case["mp4_sha256"]:
            raise ValueError(f"{folder.name}: incorrect MP4 hash")
        target = output / folder.name
        target.mkdir()
        delivered = observations(args, case, target, clip)
        observations_by_case[folder.name] = {"objective": case["objective"], "evidence": case["evidence"],
                                             "delivered": delivered}
        persist(target / "observations.json", delivered)
    models = read(ROOT / "models.json")
    for key in ("deepseek", "mistral-small"):
        with writer(args, args.models / models[key]["file"], output / f"{key}.log") as endpoint:
            for name, packet in observations_by_case.items():
                try:
                    result = editorial(endpoint, packet)
                except (ValueError, OSError) as error:
                    result = {"status": "needs_review", "reason": f"invalid local response: {error}"}
                persist(output / name / f"{key}.json", result)


def score(label_file, results):
    labels = read(label_file)
    if set(labels.values()) != {"good", "bad"}:
        raise ValueError("score requires both independently labeled good and bad cases")
    counts = {}
    models = ("deepseek", "mistral-small")
    for name in (*models, "agreement"):
        positives, negatives = [], []
        for key, classification in labels.items():
            if Path(key).name != key or key in {".", ".."}:
                raise ValueError("invalid opaque case identifier")
            votes = [read(results / key / f"{model}.json")["status"] for model in models]
            accepts = all(v == "accepted" for v in votes) if name == "agreement" else votes[models.index(name)] == "accepted"
            (positives if classification == "good" else negatives).append(accepts)
        counts[name] = {"incorrectly_accepted": sum(negatives), "bad_total": len(negatives),
                        "unnecessarily_withheld": positives.count(False), "good_total": len(positives)}
    return counts


def main():
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    run = sub.add_parser("run")
    for name in ("packets", "output", "frames", "video"):
        run.add_argument(name, type=Path)
    defaults = {"fresh": "ai/storyboard-rehearsal/fresh", "ffmpeg": "ai/tools/media/bin/ffmpeg",
                "models": "ai/storyboard-rehearsal/writer/models",
                "runtime": "ai/storyboard-rehearsal/writer/runtime/build/bin/llama-server",
                "lease": "ai/storyboard-build/v2/gpu.lock"}
    for name, relative in defaults.items():
        run.add_argument("--" + name, type=Path, default=home / relative)
    count = sub.add_parser("score")
    for name in ("labels", "results"):
        count.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.mode == "run":
        os.environ.setdefault("STORY_VISION_MODEL", str(args.fresh / "models/vision/qwen3-vl-8b"))
        calibrate(args)
    else:
        print(json.dumps(score(args.labels, args.results), indent=2))


if __name__ == "__main__":
    main()
