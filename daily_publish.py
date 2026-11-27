"""Publish only matching local and independent audit records to a new review gallery."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from daily_evidence import digest


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def publish(source, audit_file, destination):
    audit = read(audit_file)
    records, credits = [], {}
    for slot, judgment in sorted(audit.items()):
        if len(slot) != 2 or not slot.isascii() or not slot.isdecimal():
            raise ValueError("audit must use two-digit brief slots")
        case = source / slot
        outcome = read(case / "first-outcome.json")
        if outcome["status"] != "accepted" or judgment["status"] != "accepted":
            continue
        local = read(case / "local-verdict.json")
        clip = case / "video.mp4"
        hashes = {sha(clip), judgment["mp4_sha256"], local["mp4_sha256"], outcome["mp4_sha256"]}
        if (len(hashes) != 1 or local["status"] != "accepted" or digest(local) != outcome["verdict_sha256"]
                or judgment["freeze_sha256"] != outcome["freeze_sha256"]):
            raise ValueError(f"{slot}: film, local outcome and audit do not bind to the same bytes/config")
        manifest = read(case / "manifest.json")
        if digest(manifest) != local["manifest_sha256"]:
            raise ValueError(f"{slot}: reviewed manifest changed")
        credits[slot] = list({r["sha256"]: r for row in manifest["panels"]
                             if (r := row.get("daily_visual", {}).get("rights"))}.values())
        records.append((slot, clip, hashes.pop(), judgment["reason"]))
    if not records:
        raise ValueError("no independently audited first-pass films eligible for publication")
    if destination.exists():
        raise ValueError("existing gallery will not be overwritten")
    with TemporaryDirectory(dir=destination.parent) as folder:
        stage = Path(folder) / "ready"
        stage.mkdir()
        playlist = ["#EXTM3U"]
        key = ["# Daily review key", ""]
        for slot, clip, expected, reason in records:
            name = f"{slot}.mp4"
            copy = stage / name
            shutil.copyfile(clip, copy)
            if sha(copy) != expected:
                raise ValueError(f"{slot}: staged copy hash mismatch")
            subprocess.run(["gst-launch-1.0", "-q", "playbin", f"uri={copy.resolve().as_uri()}",
                            "audio-sink=fakesink sync=false", "video-sink=fakesink sync=false"],
                           stdin=subprocess.DEVNULL, check=True, timeout=310)
            playlist.append(name)
            key.extend([f"## {slot}", "", reason, ""])
        (stage / "Playlist.m3u").write_text("\n".join(playlist) + "\n")
        (stage / "Review key.md").write_text("\n".join(key))
        (stage / "Image attribution.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n")
        stage.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "audit", "destination"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    publish(args.source, args.audit, args.destination)
