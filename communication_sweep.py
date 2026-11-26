"""Fixed-brief comparisons with a durable receipt per caller submission."""
import argparse
import csv
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from storygen import COMMUNICATION_SKILL, ROOT, read, save

LEGACY = {"B04": "education", "B05": "education", "B16": "education",
          "B18": "education", "B01": "comparison", "B03": "comparison"}


def rows(path):
    with path.open() as f:
        return list(csv.reader((line for line in f if not line.startswith("#")), delimiter="\t"))


def corpus(path, legacy=False):
    items = {}
    if legacy:
        for key, family, _, topic, takeaway, facts, question, answer, evidence in rows(ROOT / "benchmark/first20.tsv"):
            if key in LEGACY:
                items[key] = (topic, f"Help a beginner answer: {question}", takeaway,
                              "A curious beginner watching on a phone", "Patient and direct",
                              facts, f"{question} Expected: {answer} Visible evidence: {evidence}",
                              LEGACY[key], family)
    for key, purpose, group, topic, objective, takeaway, audience, tone, facts, evidence in rows(path):
        if key in items:
            raise ValueError(f"duplicate item {key}")
        items[key] = (topic, objective, takeaway, audience, tone, facts, evidence, purpose, group)
    return items


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commit(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def run(args):
    manifest = read(ROOT / "benchmark/communication/freeze.json")
    rubric_sha = digest(ROOT / "benchmark/communication/RUBRIC.md")
    if rubric_sha != manifest["rubric_sha256"]:
        raise ValueError("evaluation rubric does not match frozen partition")
    if digest(ROOT / "benchmark/first20.tsv") != manifest["legacy_sha256"]:
        raise ValueError("legacy inputs do not match frozen development partition")
    provenance = {
        "model": args.model, "model_pin": read(ROOT / "models.json")[args.model],
        "voice": "heart", "writer": commit(ROOT), "frames": commit(args.frames), "video": commit(args.video),
        "endpoint": args.video_url, "skill_sha256": digest(COMMUNICATION_SKILL),
        "rubric_sha256": rubric_sha, "evaluator": "openai/gpt-6.2-sol",
    }
    if args.partition == "sealed":
        if not args.selection:
            raise ValueError("sealed run requires the frozen selection record")
        selection = read(args.selection)
        for key, value in provenance.items():
            if selection.get(key) != value:
                raise ValueError(f"sealed selection differs on {key}")
        from communication_score import score
        validation_run = Path(selection["validation_run"])
        validated = read(validation_run / "freeze.json")
        if validated["partition"] != "validation" or any(validated.get(k) != v for k, v in provenance.items()):
            raise ValueError("sealed selection must reference validation of the same frozen combination")
        summary = score(validation_run)
        if summary["planned"] != 20 or any(summary["video"].get(k) for k in ("pending", "unjudged")):
            raise ValueError("validate and adjudicate all 20 validation cases before opening sealed inputs")
        # Place the receipt beside the private partition so a different
        # result directory or model cannot accidentally reopen the set.
        receipt = args.dataset.with_suffix(".opening.json")
        opening = {"out": str(args.out.resolve()), "selection_sha256": digest(args.selection)}
        try:
            with receipt.open("x") as f:
                json.dump(opening, f)
        except FileExistsError:
            if read(receipt) != opening:
                raise ValueError("sealed set was already opened for a different run")
    if digest(args.dataset) != manifest["sha256"][args.partition]:
        raise ValueError("dataset does not match frozen partition")
    all_items = corpus(args.dataset, args.partition == "development")
    choices = list(all_items)
    if args.partition == "development":
        if args.ids:
            choices = args.ids
        elif args.broader:
            choices = [k for k in choices if k.startswith("D")]
        else:
            choices = [k for k in choices if not k.startswith("D")]
    if len(set(choices)) != len(choices) or any(k not in all_items for k in choices):
        raise ValueError("unknown or duplicate case")
    config = {**provenance, "case_ids": choices, "partition": args.partition,
              "dataset_sha256": manifest["sha256"][args.partition]}
    frozen = args.out / "freeze.json"
    if frozen.exists() and read(frozen) != config:
        raise ValueError("resume must use the exact original run configuration")
    save(frozen, config)
    for key in choices:
        topic, objective, takeaway, audience, tone, facts, evidence, purpose, group = all_items[key]
        folder = args.out / key
        folder.mkdir(exist_ok=True)
        if any((folder / f).exists() for f in ("outcome.json", "result.json", "writer-refusal.json")):
            continue
        brief = {"schema_version": "1.0", "topic": topic, "objective": objective, "takeaway": takeaway,
                 "audience": audience, "tone": tone, "visual_signature": "market" if key == "B01" else "paper",
                 "source_notes": [{"kind": "fact", "text": fact} for fact in facts.split("|")]}
        save(folder / "brief.json", brief)
        save(folder / "oracle.json", {"objective": objective, "takeaway": takeaway,
                                     "evidence": evidence, "purpose": purpose, "group": group})
        cmd = [sys.executable, "-B", str(ROOT / "storygen.py"), "run", str(folder / "brief.json"),
               "--out", str(folder), "--model", args.model, "--voice", "heart",
               "--video-url", args.video_url, "--validator-python", str(args.validator_python),
               "--frames-repo", str(args.frames), "--video-repo", str(args.video)]
        with (folder / "run.log").open("a") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        print(key, result.returncode, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("out", "dataset", "frames", "video", "validator-python"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--partition", choices=("development", "validation", "sealed"), default="development")
    p.add_argument("--selection", type=Path)
    p.add_argument("--broader", action="store_true")
    p.add_argument("--id", dest="ids", action="append")
    p.add_argument("--model", required=True)
    p.add_argument("--video-url", required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / ".sweep.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args)


if __name__ == "__main__":
    main()
