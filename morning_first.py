"""Freeze and run the twenty morning briefs through the ordinary writer/video CLI."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from storygen import communication_skill, read, save


def freeze(source, root):
    with source.open() as f:
        lines = list(csv.reader(f, delimiter="\t"))
    if [row[0] for row in lines] != [f"{i:02}" for i in range(1, 21)]:
        raise ValueError("expected 20 numbered showcase briefs")
    rows = {}
    for slot, topic, objective, audience, tone, takeaway, facts, success in lines:
        rows[slot] = {"brief": {"schema_version": "1.0", "topic": topic, "objective": objective,
                              "audience": audience, "tone": tone, "takeaway": takeaway,
                              "visual_signature": "paper",
                              "source_notes": [{"kind": "fact", "text": fact} for fact in facts.split("|")]},
                      "success": success}
    # The comparison intentionally changes only the communication objective.
    def invariant(s):
        return {k: v for k, v in rows[s]["brief"].items() if k != "objective"}
    assert invariant("01") == invariant("02")
    target = root / "briefs.json"
    if target.exists() and read(target) != rows:
        raise ValueError("showcase briefs are already frozen")
    save(target, rows)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("root", type=Path)
    p.add_argument("--video-url", required=True)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--validator-python", required=True)
    p.add_argument("--model", default="mistral-small")
    p.add_argument("--skill", default="v8")
    p.add_argument("--freeze-only", action="store_true")
    p.add_argument("--slot", action="append")
    a = p.parse_args()
    a.root.mkdir(parents=True, exist_ok=True)
    rows = freeze(a.source, a.root)
    project = Path(__file__).resolve().parent
    commit = lambda path: subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    config = {"case_ids": list(rows), "model": a.model, "voice": "heart", "skill": a.skill,
              "skill_sha256": hashlib.sha256(communication_skill(a.skill).read_bytes()).hexdigest(),
              "briefs_sha256": hashlib.sha256((a.root / "briefs.json").read_bytes()).hexdigest(),
              "story": commit(project), "frames": commit(a.frames), "video": commit(a.video),
              "endpoint": a.video_url, "outcome_scope": "showcase, not benchmark"}
    manifest = a.root / "freeze.json"
    if manifest.exists() and read(manifest) != config:
        raise ValueError("showcase configuration changed")
    save(manifest, config)
    if a.freeze_only:
        return
    for slot in a.slot or rows:
        folder = a.root / slot
        folder.mkdir(exist_ok=True)
        if any((folder / x).exists() for x in ("outcome.json", "result.json", "writer-refusal.json")):
            continue
        brief = folder / "brief.json"
        save(brief, rows[slot]["brief"])
        cmd = [sys.executable, "-B", str(project / "storygen.py"), "run", str(brief), "--out", str(folder),
               "--model", a.model, "--communication-skill", a.skill, "--voice", "heart",
               "--video-url", a.video_url, "--validator-python", a.validator_python,
               "--frames-repo", str(a.frames), "--video-repo", str(a.video)]
        with (folder / "run.log").open("a") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        save(folder / "cli.json", {"returncode": result.returncode})
        print(slot, result.returncode, flush=True)


if __name__ == "__main__":
    main()
