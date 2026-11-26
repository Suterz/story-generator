"""Build separate blind review packets and a private reveal key."""
import argparse
import hashlib
from pathlib import Path
import shutil

from storygen import read, save


def collect(runs, output, nonce):
    blind, key = output / "blind", output / "reveal"
    blind.mkdir(parents=True, exist_ok=True)
    key.mkdir(parents=True, exist_ok=True)
    for run in runs:
        for case in read(run / "freeze.json")["case_ids"]:
            folder = run / case
            if not (folder / "story.json").exists():
                continue
            anon = hashlib.sha256(f"{nonce}:{run.resolve()}:{case}".encode()).hexdigest()[:12]
            dest = blind / anon
            dest.mkdir(exist_ok=True)
            story = read(folder / "story.json")
            save(dest / "script.json", [{"text": item["text"], "caption": item.get("caption")}
                                         for item in story["script"]])
            if (folder / "video.mp4").exists():
                outcome = read(folder / "outcome.json")
                with (folder / "video.mp4").open("rb") as f:
                    assert hashlib.file_digest(f, "sha256").hexdigest() == outcome["download_sha256"]
                shutil.copyfile(folder / "video.mp4", dest / "video.mp4")
                target = dest / "phone"
                shutil.copytree(folder / "decoded", target, dirs_exist_ok=True)
                manifest = read(folder / "manifest.json")
                review = next(item for item in read(run / "review-index.json") if item["case"] == case)
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
