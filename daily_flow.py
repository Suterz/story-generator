"""Own daily attempts and draft delivery independently of human approval."""
from argparse import Namespace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from daily_evidence import digest, persist


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def deliver(attempt, destination):
    outcome = read(attempt / "first-outcome.json")
    verdict = read(attempt / "local-verdict.json")
    manifest = read(attempt / "manifest.json")
    clip = attempt / "video.mp4"
    if (outcome["status"] != "accepted" or verdict["status"] != "accepted"
            or digest(verdict) != outcome["verdict_sha256"]
            or digest(manifest) != verdict["manifest_sha256"]
            or verdict["configuration"]["freeze_sha256"] != outcome["freeze_sha256"]
            or len({sha(clip), verdict["mp4_sha256"], outcome["mp4_sha256"]}) != 1):
        raise ValueError("local draft outcome, configuration, assets and media disagree")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha(destination / "video.mp4") != outcome["mp4_sha256"] or read(destination / "outcome.json") != outcome:
            raise ValueError("existing draft belongs to a different adjudicated attempt")
        return
    with TemporaryDirectory(dir=destination.parent) as directory:
        stage = Path(directory) / "draft"
        stage.mkdir()
        copied = stage / "video.mp4"
        shutil.copyfile(clip, copied)
        if sha(copied) != outcome["mp4_sha256"]:
            raise ValueError("draft copy hash mismatch")
        media = Path(os.getenv("DAILY_MEDIA", Path.home() / "ai/tools/media/bin"))
        subprocess.run([str(media / "ffmpeg"), "-v", "error", "-xerror", "-i", str(copied),
                        "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
                       check=True, timeout=310)
        next_chapter = next(iter(manifest.get("chapter_starts", [])[1:]), None)
        cut = next((row["start_sample"] / 48000 for row in manifest.get("speech_groups", [])
                    if row["first_utterance"] == next_chapter), 25)
        opening = stage / "opening.mp4"
        subprocess.run([str(media / "ffmpeg"), "-v", "error", "-xerror", "-i", str(copied),
                        "-t", str(min(cut, 45)), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", str(opening)], check=True, timeout=150)
        credits = {}
        for row in manifest["panels"]:
            rights = row.get("daily_visual", {}).get("rights")
            if rights:
                if not rights.get("commercial_editorial") or not rights.get("credit"):
                    raise ValueError(f'{row["id"]}: documentary credit or rights missing')
                credits[rights["sha256"]] = rights
        persist(stage / "credits.json", list(credits.values()))
        persist(stage / "outcome.json", outcome)
        persist(stage / "media-sha256.json", {"video.mp4": sha(copied), "opening.mp4": sha(opening)})
        persist(stage / "scene-decisions.json", [{"id": row["id"], "frame_sha256": row["sha256"],
                                                 **row.get("daily_visual", {})}
                                                for row in manifest["panels"]])
        if (attempt / "phone").is_dir():
            shutil.copytree(attempt / "phone", stage / "phone")
        if (attempt / "decoded-review.json").is_file():
            shutil.copyfile(attempt / "decoded-review.json", stage / "decoded-review.json")
        shutil.copyfile(attempt / "local-verdict.json", stage / "local-verdict.json")
        stage.rename(destination)


def ordinary_run(args):
    from daily import run_daily

    root = args.out
    freeze = os.getenv("DAILY_FREEZE")
    if not freeze:
        raise ValueError("daily run requires DAILY_FREEZE")
    identity = {"brief_file": sha(args.input), "freeze": sha(Path(freeze)), "voice": args.voice,
                "model": args.model, "endpoint": args.video_url, "adapter": args.daily,
                "skill": args.episode_skill, "runtime": str(args.runtime), "weights": str(args.models)}
    binding = root / "workflow-inputs.json"
    if binding.exists() and read(binding) != identity:
        raise ValueError("daily workflow inputs changed; use a new run directory")
    persist(binding, identity)
    attempts = []
    gallery = os.getenv("DAILY_DRAFT_GALLERY")
    for i in range(2):
        attempt = root / f"attempt-{i+1:02d}"
        attempt.mkdir(exist_ok=True)
        feedback = attempts[-1]["reason"] if i else None
        if i:
            for name in ("ordinary-normalized.json", "claim-ledger.json", "evidence-complete.json", "retrieval.json"):
                source = root / "attempt-01" / name
                if source.is_file() and not (attempt / name).exists():
                    shutil.copyfile(source, attempt / name)
        run_daily(Namespace(**{**vars(args), "out": attempt, "repair_feedback": feedback}))
        result = read(attempt / "first-outcome.json")
        attempts.append(result)
        if i == 0:
            first = root / "first-outcome.json"
            if first.exists() and read(first) != result:
                raise ValueError("the preserved first outcome changed")
            if not first.exists():
                persist(first, result)
        if not (result.get("renderer", {}).get("phase") in {"alignment", "duration"}
                or (result["status"] == "withheld" and result.get("stage") == "authoring")
                or (result["status"] == "needs_review" and result.get("stage") == "editorial")):
            break
    final = {**result, "first_attempt": attempts[0]["status"], "attempt_count": len(attempts),
             "automatic_revision_count": len(attempts) - 1 + sum(len(a["automatic_revisions"]) for a in attempts)}
    if result["status"] == "accepted" and gallery:
        destination = Path(gallery) / (root.name + "-" + digest(identity)[:12])
        try:
            deliver(attempt, destination)
            final["draft_gallery"] = str(destination)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
            final.update(status="withheld", reason=f"draft delivery: {error}")
    persist(root / "terminal-outcome.json", final)
    print(json.dumps(final, ensure_ascii=False))
