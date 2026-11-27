"""Run a presealed queue once after its release and network controls are verified."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

from daily_evidence import persist


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify_freeze(path):
    freeze = read(path)
    if set(freeze["repositories"]) != {"story", "frames", "video"} or not freeze["files"]:
        raise ValueError("freeze must pin three repositories and runtime artifacts")
    for record in freeze["repositories"].values():
        repo = record["path"]
        head = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", repo, "status", "--porcelain"], text=True)
        if head != record["commit"] or status:
            raise ValueError(f"checkout is not at its clean freeze: {repo}")
    for name, expected in freeze["files"].items():
        if sha(Path(name)) != expected:
            raise ValueError(f"frozen runtime artifact changed: {name}")
    return freeze


def block_openai():
    populated = sorted(key for key, value in os.environ.items() if value and "OPENAI" in key.upper())
    if populated:
        raise ValueError(f"OpenAI-related settings present: {', '.join(populated)}")
    for host in ("api.openai.com", "chatgpt.com"):
        result = subprocess.run(["curl", "--noproxy", "*", "--silent", "--output", "/dev/null",
                                 "--max-time", "5", "https://" + host], check=False)
        if result.returncode == 0:
            raise ValueError(f"OpenAI connectivity control reached {host}")


def run(args):
    block_openai()
    freeze = verify_freeze(args.freeze)
    release = read(args.seal)
    cases = release["briefs"]
    if sorted(cases) != ["01", "02", "03", "04", "05"] or not release["expected_outcome_commitment"]:
        raise ValueError("sealed release requires five brief hashes and a separate outcome commitment")
    for slot, expected in cases.items():
        if sha(args.briefs / f"{slot}.json") != expected:
            raise ValueError(f"brief changed after sealing: {slot}")
    repos = freeze["repositories"]
    runtime = freeze["runtime"]
    endpoint = urlsplit(runtime["video_url"])
    if endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1":
        raise ValueError("video service must be on loopback")
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    environment = {**os.environ, "DAILY_FREEZE": str(args.freeze.resolve()),
                   "DAILY_FRAMES_REPO": repos["frames"]["path"], "DAILY_VIDEO_REPO": repos["video"]["path"],
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    persist(output / "batch.json", {"seal_sha256": sha(args.seal), "freeze_sha256": sha(args.freeze),
                                   "started": datetime.now(timezone.utc).isoformat()})
    for slot in sorted(cases):
        folder = output / slot
        folder.mkdir()
        command = [sys.executable, "-B", str(Path(repos["story"]["path"]) / "storygen.py"),
                   "run", str(args.briefs / f"{slot}.json"), "--out", str(folder),
                   "--model", runtime["writer"], "--voice", "heart",
                   "--video-url", runtime["video_url"], "--runtime", runtime["llama"],
                   "--models", runtime["weights"], "--lease", runtime["lease"],
                   "--validator-python", runtime["validator_python"],
                   "--frames-repo", repos["frames"]["path"], "--video-repo", repos["video"]["path"]]
        started = time.monotonic()
        with (folder / "run.log").open("w") as log:
            try:
                rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    env=environment, check=False, timeout=5400).returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
        first = folder / "first-outcome.json"
        if not first.exists():
            persist(first, {"status": "infrastructure_stop", "reason": f"runner exit: {rc}",
                            "brief_file_sha256": cases[slot], "freeze_sha256": sha(args.freeze)})
        persist(folder / "measurement.json", {"wall_seconds": time.monotonic() - started,
                    "exit": rc, "first_outcome_sha256": sha(first), "manual_interventions_observed_by_runner": 0})
        first.chmod(0o444)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("freeze", "seal", "briefs", "output"):
        parser.add_argument(arg, type=Path)
    run(parser.parse_args())
