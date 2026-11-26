"""Prepare or run a frozen development sweep without exposing its scoring rows."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from storygen import SKILL, save


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out", type=Path)
    p.add_argument("--model", default="qwen")
    p.add_argument("--video-url", default="http://127.0.0.1:8893")
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--write-only", action="store_true")
    p.add_argument("--validator-python", type=Path)
    p.add_argument("--id", action="append", dest="ids")
    a = p.parse_args()
    project = Path(__file__).resolve().parent
    dataset = project / "benchmark/first20.tsv"
    with dataset.open() as stream:
        rows = list(csv.reader((line for line in stream if not line.startswith("#")), delimiter="\t"))
    assert len(rows) == len({row[0] for row in rows}) == 20
    commit = lambda tree: subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], text=True).strip()
    ids = a.ids or [row[0] for row in rows]
    config = {"writer": commit(project), "frames": commit(a.frames), "video": commit(a.video),
              "dataset_sha256": fingerprint(dataset), "model": a.model, "case_ids": ids,
              "model_manifest_sha256": fingerprint(project / "models.json"),
              "skill_sha256": fingerprint(SKILL),
              "evaluator_sha256": fingerprint(project / "inspect_run.py"),
              "mode": "write" if a.write_only else "run", "video_url": a.video_url,
              "native_validation": a.validator_python is not None}
    env = os.environ.copy()
    if a.validator_python is not None:
        env["STORYGEN_VALIDATOR_PYTHON"] = str(a.validator_python)
        env["STORYGEN_RENDERER_SOURCES"] = os.pathsep.join(str(tree / "src") for tree in (a.frames, a.video))
    a.out.mkdir(parents=True, exist_ok=True)
    freeze = a.out / "freeze.json"
    if freeze.exists() and json.loads(freeze.read_text()) != config:
        raise SystemExit("frozen sweep configuration changed; choose a different store")
    save(freeze, config)
    for case, family, provenance, topic, takeaway, facts, question, answer, visible in rows:
        if case not in ids:
            continue
        folder = a.out / case
        folder.mkdir(exist_ok=True)
        fields = {"topic": topic, "takeaway": takeaway, "required_facts": facts.split("|"),
                  "audience": "A beginner", "signature": "market" if case == "B01" else "paper"}
        brief = folder / "brief.json"
        save(brief, fields)
        save(folder / "oracle.json", dict(family=family, provenance=provenance, question=question,
                                         answer=answer, visible=visible))
        command = [sys.executable, "-B", str(project / "storygen.py"), config["mode"], str(brief),
                   "--out", str(folder), "--model", a.model, "--video-url", a.video_url]
        with (folder / "run.log").open("a") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(case, result.returncode, flush=True)


if __name__ == "__main__":
    main()
