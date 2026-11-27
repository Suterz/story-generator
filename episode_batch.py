"""Run a frozen episode candidate through storygen's public entry point."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

from storygen import ROOT, read, save


def file_hash(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def revision(path):
    if subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True).strip():
        raise ValueError(f"finish or isolate changes in {path} before freezing")
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--video-url", required=True)
    p.add_argument("--validator-python", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--voice", choices=("heart", "ryan"), required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--include-transfer", action="store_true")
    p.add_argument("--freeze-only", action="store_true")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    briefs = sorted((ROOT / "episodes/flagships").glob("*.json"))
    transfer = sorted((ROOT / "episodes/transfer").glob("*.json"))
    model = read(ROOT / "models.json")[a.model]
    actual = file_hash(a.weights / model["file"])
    if actual != model["sha256"]:
        raise ValueError("writer weights differ from the selected model pin")
    config = {"story": revision(ROOT), "frames": revision(a.frames), "video": revision(a.video),
              "runtime": file_hash(a.runtime), "model": model, "voice": a.voice, "policy": "routed",
              "writer_revisions_per_state": 1, "native_frame_repair_budget": 0,
              "validator_python": a.validator_python, "video_url": a.video_url,
              "source_packs": {name: file_hash(ROOT / "episodes" / name)
                               for name in ("citation-source.json", "coastlines.json")},
              "briefs": {path.stem: file_hash(path) for path in briefs + transfer}}
    manifest = a.output / "freeze.json"
    if manifest.exists() and read(manifest) != config:
        raise ValueError("release inputs changed; use a fresh candidate store")
    if not manifest.exists():
        save(manifest, config)
    if a.freeze_only:
        return
    if a.include_transfer:
        verdicts = [read(a.output / file.stem / "independent-judgment.json") for file in briefs]
        for row, spec in zip(verdicts, briefs, strict=True):
            case = a.output / spec.stem
            if (row["verdict"] != "verified_pass" or row["sha256"] != file_hash(case / "video.mp4")
                    or row["freeze_sha256"] != file_hash(manifest)):
                raise ValueError("all flagships require hash-bound passes before transfer generation")
        briefs = transfer
    for path in briefs:
        case = a.output / path.stem
        case.mkdir(exist_ok=True)
        if (case / "outcome.json").is_file() or (case / "result.json").is_file():
            continue
        command = [sys.executable, "-B", str(ROOT / "storygen.py"), "run", str(path),
                   "--out", str(case), "--model", a.model, "--models", str(a.weights),
                   "--runtime", str(a.runtime), "--voice", a.voice, "--episode-skill", "routed",
                   "--video-url", a.video_url, "--validator-python", a.validator_python,
                   "--frames-repo", str(a.frames), "--video-repo", str(a.video)]
        with (case / "run.log").open("a") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        print(path.stem, result.returncode, flush=True)


if __name__ == "__main__":
    main()
