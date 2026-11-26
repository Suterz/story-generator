"""Publish review-approved, hash-matched MP4s and a neutral local playlist."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote


def get(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def synctext(path, text):
    temp = path.with_suffix(".tmp")
    temp.write_text(text)
    temp.replace(path)


def fetch(host, remote, dest):
    temp = dest.with_name("." + dest.name + ".incoming")
    subprocess.run(["scp", "-q", f"{host}:{remote}", str(temp)], check=True, timeout=90)
    return temp


def first_outcome(path):
    rejected = path / "incorrect-accepted.json"
    if rejected.exists():
        record = get(rejected)
        return "incorrect_accepted", record.get("reason")
    for name in ("outcome", "result", "writer-refusal", "cli"):
        file = path / f"{name}.json"
        if file.exists():
            data = get(file)
            status = data.get("state") or data.get("status") or ("writer_refusal" if name == "writer-refusal" else "operational_failure")
            reason = data.get("reason") or data.get("error")
            if not reason and data.get("diagnostics"):
                reason = data["diagnostics"][-1]
            return status, reason
    return "pending", None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("gallery", type=Path)
    p.add_argument("--host", default="zelio-suter@zelio-server")
    p.add_argument("--remote", default="/home/zelio-suter/ai/morning-review")
    a = p.parse_args()
    root, evidence = a.gallery, a.gallery / "Evidence"
    watch = root / "Watch first"
    watch.mkdir(exist_ok=True)
    evidence.mkdir(exist_ok=True)
    subprocess.run(["rsync", "-a", "--prune-empty-dirs",
                    "--include=/first/", "--include=/assisted/", "--include=/assisted-refined/",
                    "--exclude=/*", "--include=*/", "--include=outcome.json", "--include=result.json",
                    "--include=writer-refusal.json", "--include=story.json", "--include=manifest.json",
                    "--include=submission.json", "--include=gallery.json", "--include=receipt.json",
                    "--include=cli.json", "--include=phone.png", "--include=pause-proof.json",
                    "--include=mux-speech.json", "--include=writer-attempt-*.json",
                    "--include=mux-pause-proof.json", "--include=mux-bell-proof.json",
                    "--include=incorrect-accepted.json", "--include=operational.json",
                    "--exclude=*", f"{a.host}:{a.remote}/", str(evidence / "Runs")], check=True, timeout=100)
    briefs = get(evidence / "Frozen briefs.json")
    freeze = get(evidence / "Freeze.json")
    verdict_file = evidence / "Sol review.json"
    verdicts = get(verdict_file) if verdict_file.exists() else {}
    published = evidence / "Published clips.json"
    index = get(published) if published.exists() else {}
    counts = dict.fromkeys(("autonomous first pass", "automatic repair", "agent-assisted"), 0)
    initial_counts = Counter()
    playlist = ["#EXTM3U"]
    key = [
        "# Morning Review — key", "",
        "Watch the numbered clips before opening this key. The numbers are the frozen slots, not rankings.",
        "",
        f"The independent first run used **{freeze['model']} / skill {freeze['skill']} / {freeze['voice']}**, "
        f"writer `{freeze['story'][:7]}`, frames `{freeze['frames'][:7]}`, video `{freeze['video'][:7]}`.",
        "This is a review showcase, separate from the benchmark and its sealed set.",
        "Writer refusals are preserved in the first-submission results; native preflight withholds their invalid requests before a renderer POST.",
        "Sol inspected decoded phone frames and scripts/independent transcript where available. "
        "The evidence folder distinguishes transcripts of the delivered MP4 from source-audio checks. "
        "Warmth, perceived pacing, and emotional impact are for your listening review.",
    ]
    for slot, row in briefs.items():
        brief = row["brief"]
        first = evidence / "Runs" / "first" / slot
        original, issue = first_outcome(first)
        initial_counts[original] += 1
        key.extend(("", f"## {slot} — {brief['topic']}", "",
                    f"**Objective:** {brief['objective']}",
                    f"**Audience / tone:** {brief['audience']} · {brief['tone']}.",
                    f"**Takeaway:** {brief['takeaway']}",
                    "**Authorized facts:** " + " ".join(n["text"] for n in brief["source_notes"]),
                    f"**Success check:** {row['success']}", f"**First outcome:** `{original}`."))
        if issue:
            key.append(f"**Initial diagnostic:** {issue.replace(chr(10), ' ')[:350]}")
        entry = verdicts.get(slot)
        if not entry:
            key.append("**Final:** Pending review or delivery.")
            continue
        if not entry.get("arm"):
            key.append(f"**Final:** {entry['verdict']}. **Blocker:** {entry['note']}")
            continue
        arm = entry["arm"]
        candidate = evidence / "Runs" / arm / slot
        status = get(candidate / "outcome.json")
        manifest = get(candidate / "manifest.json")
        expected = status["download_sha256"]
        if expected != entry["sha256"] or status["state"] != "succeeded":
            raise ValueError(f"{slot}: judgment does not bind to a terminal returned video")
        duration = manifest["verification"]["expected_duration"]
        if not 0 < duration < 45:
            raise ValueError(f"{slot}: invalid duration {duration}")
        dest = watch / f"{slot}.mp4"
        if dest.exists() and digest(dest) != expected:
            raise ValueError(f"{slot}: existing published clip differs; preserve it before replacing")
        if slot not in index or not dest.exists():
            temp = fetch(a.host, f"{a.remote}/{arm}/{slot}/video.mp4", dest) if not dest.exists() else dest
            if digest(temp) != expected:
                raise ValueError(f"{slot}: copy hash mismatch")
            subprocess.run(["gst-launch-1.0", "-q", "playbin", f"uri={temp.resolve().as_uri()}",
                            "video-sink=fakesink sync=false", "audio-sink=fakesink sync=false"],
                           check=True, timeout=60, capture_output=True, stdin=subprocess.DEVNULL)
            if temp != dest:
                temp.replace(dest)
            index[slot] = {"sha256": expected, "seconds": duration, "decoder": "XPS GStreamer playbin"}
        counts[entry["assistance"]] += 1
        playlist.extend((f"#EXTINF:{duration:.3f},{slot}", quote(dest.name)))
        key.extend((f"**Delivery:** [Watch {slot}](Watch%20first/{slot}.mp4) · {duration:.1f} s · **{entry['assistance']}**.",
                    f"**Model and skill:** {entry['method']}.",
                    f"**Verdict:** {entry['verdict']}. **Revisit {entry['time']}:** {entry['note']}"))
    summary = f"**Playable and verified on the XPS: {sum(counts.values())}/20.** " + ", ".join(
        f"{count} {name}" for name, count in counts.items()) + "."
    key.insert(2, summary + "\n")
    key.insert(3, "**Initial outcomes (all 20 slots):** " + ", ".join(
        f"{count} {status.replace('_', ' ')}" for status, count in initial_counts.items()) + ".\n")
    key.extend(("", "## Suggested comparisons", "",
                "- **01 and 02:** Same door and fact. Compare the immediate practical clue with the acknowledgment of a long day before it.",
                "- **12:** Listen to the silence before *slowly* in the two readings; the held image takes attention away from visual cuts.",
                "- **17 and 18:** A visible matching patch resolves a mystery; moving a bag carries the meaning of kindness without a spoken moral."))
    synctext(watch / "Playlist.m3u", "\n".join(playlist) + "\n")
    synctext(root / "Review key.md", "\n".join(key) + "\n")
    synctext(published, json.dumps(index, indent=2) + "\n")
    print(summary)


if __name__ == "__main__":
    main()
