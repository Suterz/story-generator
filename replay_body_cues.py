"""Prepared development replay: preserve the original speech checkpoints and repair cue spelling."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from daily_evidence import persist


def sha(data):
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    from video_renderer.api import EpisodeVideo, keyed_job

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("old_job", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("store", type=Path)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    story = json.loads((args.attempt / "story.json").read_text())
    script = {row["id"]: row["text"] for row in story["script"]}
    count = 0
    for beat in story["beats"]:
        if "phrase" in beat["cue"]:
            cue = " ".join(script[beat["cue"]["utterance_id"]].split()[:3])
            count += cue != beat["cue"]["phrase"]
            beat["cue"]["phrase"] = cue
    digest = sha(json.dumps(story, sort_keys=True).encode())
    key = "storygen-" + sha(f"{args.output.resolve()}:{digest}".encode())
    job_id = keyed_job(key)
    request = EpisodeVideo.model_validate(story).model_dump(mode="json")
    original = json.loads((args.old_job / "request.json").read_text())
    if original["script"] != request["script"] or original["voice_profile"] != request["voice_profile"]:
        raise ValueError("cannot reuse narration when the words or voice changed")
    job = args.store / job_id
    job.mkdir(parents=True, exist_ok=False)
    for source in sorted(args.old_job.glob("group-*.json")):
        if not source.stem.rsplit("-", 1)[-1].isdigit():
            continue
        entry = json.loads(source.read_text())
        pcm = source.with_suffix(".pcm.wav")
        if sha(pcm.read_bytes()) != entry["wav_sha256"]:
            raise ValueError("source PCM checkpoint mismatch")
        for file in (pcm, source):
            shutil.copyfile(file, job / file.name)
    persist(job / "request.json", request)
    persist(job / "status.json", {"id": job_id, "state": "queued",
             "status_url": f"/v2/renders/{job_id}", "video_url": f"/v2/renders/{job_id}/video",
             "submission_sha256": sha(json.dumps([request, None, None], sort_keys=True).encode())})
    persist(args.output / "story.json", story)
    persist(args.output / "replay-spec.json", {"original_job": str(args.old_job), "job_id": job_id,
            "changed_cue_phrases": count, "created_from_existing_verified_speech": True})
