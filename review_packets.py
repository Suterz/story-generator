"""Build separate blind review packets and a private reveal key."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from storygen import read, save


def script_view(story):
    if not isinstance(story, dict) or not isinstance(story.get("script"), list) or not story["script"]:
        return None
    if not all(isinstance(item, dict) and isinstance(item.get("text"), str) for item in story["script"]):
        return None
    return [{"text": item["text"], "caption": item.get("caption")} for item in story["script"]]


def first_script(path):
    """Read the actual first written candidate even if preflight withheld it."""
    if not path.is_file():
        return None
    try:
        response = read(path)["response"]["choices"][0]["message"]["content"]
        return script_view(json.loads(response))
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def collect(runs, output, nonce):
    blind, key = output / "blind", output / "reveal"
    blind.mkdir(parents=True, exist_ok=True)
    key.mkdir(parents=True, exist_ok=True)
    for run in runs:
        index = run / "review-index.json"
        decoded = {row["case"]: row for row in read(index) if "frames" in row} if index.is_file() else {}
        for case in read(run / "freeze.json")["case_ids"]:
            folder = run / case
            first = first_script(folder / "writer-attempt-0.json")
            authored = script_view(read(folder / "story.json")) if (folder / "story.json").exists() else None
            if first is None and authored is None:
                continue
            anon = hashlib.sha256(f"{nonce}:{run.resolve()}:{case}".encode()).hexdigest()[:12]
            dest = blind / anon
            dest.mkdir(exist_ok=True)
            if first is not None:
                save(dest / "first-script.json", first)
            if authored is not None:
                save(dest / "script.json", authored)
            if case in decoded:
                outcome = read(folder / "outcome.json")
                with (folder / "video.mp4").open("rb") as f:
                    assert hashlib.file_digest(f, "sha256").hexdigest() == outcome["download_sha256"]
                shutil.copyfile(folder / "video.mp4", dest / "video.mp4")
                target = dest / "phone"
                shutil.copytree(folder / "decoded", target, dirs_exist_ok=True)
                manifest = read(folder / "manifest.json")
                review = decoded[case]
                save(dest / "timing.json", {"duration": review["duration"], "sample_frames": review["frames"],
                                           "beats": manifest["beats"], "caption_trace": manifest["caption_trace"],
                                           "source_asr": manifest["asr"]})
            save(key / f"{anon}.json", {"case": case, "run": str(run), "brief": read(folder / "brief.json"),
                                        "oracle": read(folder / "oracle.json")})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("runs", nargs="+", type=Path)
    p.add_argument("--nonce", required=True)
    args = p.parse_args()
    collect(args.runs, args.output, args.nonce)


if __name__ == "__main__":
    main()
