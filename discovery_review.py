"""Derive review obligations before opening the delivered media."""
from pathlib import Path
import argparse
import hashlib
import json
import fcntl
import re
import subprocess

from daily import TEXT, array, ask, obj
from daily_evidence import digest, persist
from opening_review import REVIEWERS
from review_daily import worker
from storygen import ROOT, read, writer

OBLIGATIONS = obj({"checks": array(obj({
    "rule": {**TEXT, "maxLength": 220},
    "source_quote": {**TEXT, "maxLength": 500},
}), 1, 4)})
FIND = obj({"status": {"enum": ["accepted", "failed", "uncertain"]},
            "defect": {"type": "string", "maxLength": 200},
            "quote": {"type": "string", "maxLength": 220},
            "why": {**TEXT, "maxLength": 380}})
DERIVE = ("Read only the objective and source. Derive up to four decisive checks, including exact relationships "
          "and any ordering of question versus answer. Each source_quote must be copied verbatim. Do not "
          "assume a defect, invent a location or timestamp, or infer extra requirements. A setup can show "
          "or mention a different state before explicitly rewinding.")
DISCOVER = ("Evaluate the entire delivered excerpt against its checks. Search the spoken words yourself, especially "
            "explicit counts, named membership and answers spoken before a reveal. A pictured correct end state "
            "does not excuse a false statement. Read a rewind as a change of state, not a contradiction with an "
            "earlier state. When failing, copy a short contiguous exact quote from delivered_asr, not from the source. "
            "When not failing leave quote and defect empty. Do not demand that a fair opening answer its question.")


def derive(endpoint, brief, out):
    derived = ask(endpoint, DERIVE, brief, OBLIGATIONS, 650, out / "derived-response.json")
    source = brief["evidence"]
    if any(row["source_quote"] not in source for row in derived["checks"]):
        raise ValueError("derived check did not quote the actual evidence")
    persist(out / "checks-before-observations.json", {"input_sha256": digest(brief), **derived})
    return derived["checks"]


def derive_indexed(endpoint, brief, out):
    sentences = re.split(r"(?<=[.!?])\s+", brief["evidence"])
    schema = obj({"checks": array(obj({"rule": {**TEXT, "maxLength": 220},
                                     "source_index": {"enum": list(range(len(sentences)))}}), 1, 4)})
    derived = ask(endpoint, "Derive checks only from these source sentences and objective. Select a zero-based "
                  "source index instead of copying text. Distinguish the initial state from any later state.",
                  {"objective": brief["objective"], "source_sentences": sentences}, schema, 650,
                  out / "indexed-response.json")
    checks = [{"rule": row["rule"], "source_quote": sentences[row["source_index"]]} for row in derived["checks"]]
    persist(out / "indexed-checks-before-observations.json", {"input_sha256": digest(brief), "checks": checks})
    return checks


def locate(quote, words):
    from storygen import words as tokenize

    target = tokenize(quote)
    if not target:
        return None
    stream = [(part, row) for row in words for part in tokenize(row["word"])]
    hits = [i for i in range(len(stream)) if [part for part, _ in stream[i:i+len(target)]] == target]
    if len(hits) != 1:
        return None
    i = hits[0]
    return [stream[i][1]["start"], stream[i+len(target)-1][1]["end"]]


def timed_observation_packet(target, mp4, derive_inputs, checks, words, frames):
    packet = {"mp4_sha256": mp4, "pre_media_inputs_sha256": digest(derive_inputs),
              "checks_sha256": digest(checks), "words_sha256": digest(words), "frames_sha256": digest(frames)}
    persist(target / "observations-origin.json", packet)


def run(args):
    model = read(ROOT / "models.json")["mistral-small"]
    args.output.mkdir(parents=True, exist_ok=False)
    cases = sorted(args.packets.iterdir())
    specs = {}
    # No media file is opened, decoded or inspected during expectation derivation.
    with writer(args, args.models / model["file"], args.output / "derive.log") as endpoint:
        derives = {}
        for case in cases:
            source = read(case / "packet.json")
            brief = {k: source[k] for k in ("objective", "evidence")}
            target = args.output / case.name
            target.mkdir()
            key = digest(brief)
            if key in derives:
                checks, indexed = derives[key]
                persist(target / "same-source-checks.json", {"input_sha256": key, "copied_checks": checks,
                                                            "copied_indexed_checks": indexed})
            else:
                try:
                    checks = derive(endpoint, brief, target)
                except ValueError as error:
                    checks = []
                    persist(target / "derivation-failure.json", {"reason": str(error)})
                try:
                    indexed = derive_indexed(endpoint, brief, target)
                except ValueError as error:
                    indexed = []
                    persist(target / "indexed-derivation-failure.json", {"reason": str(error)})
                derives[key] = checks, indexed
            specs[case.name] = (brief, source["mp4_sha256"], target, checks, indexed)

    packets = []
    for case in cases:
        brief, expected, target, checks, indexed = specs[case.name]
        clip = case / "video.mp4"
        actual = hashlib.sha256(clip.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"{case.name}: immutable MP4 changed")
        if args.observations:
            same = args.observations / case.name
            origin = same / "observations-origin.json"
            if not origin.exists():
                origin = same / "ordinary-observation.json"
            if read(origin)["mp4_sha256"] != actual:
                raise ValueError("observation reuse does not bind to the immutable MP4")
            packets.append((case.name, actual, target, brief, checks, indexed,
                            read(same / "actual-words.json"), read(same / "sampled-observations.json")))
            continue
        raw = target / "delivered.wav"
        subprocess.run([str(args.ffmpeg), "-v", "error", "-xerror", "-i", str(clip),
                        "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(raw)], check=True, timeout=90)
        fresh = args.fresh
        audio = worker([fresh / "venvs/v2-asr/bin/python", args.video / "src/video_renderer/speech_worker.py",
                        "asr", fresh / "speech", raw], {})
        persist(target / "actual-words.json", audio)
        seconds = int(audio[-1]["end"]) if audio else 0
        interval = min(10, max(2, seconds // 12))
        queries = []
        for stamp in range(0, seconds, interval):
            image = target / f"frame-{stamp:03}.png"
            subprocess.run([str(args.ffmpeg), "-v", "error", "-ss", str(stamp), "-i", str(clip),
                            "-frames:v", "1", "-vf", "scale=360:640", str(image)], check=True, timeout=30)
            queries.append({"images": [[f"Delivered frame at {stamp}s", str(image)]],
                            "prompt": "Transcribe the decisive labels and describe object state. Use 45 words at most."})
        with args.lease.open("a") as lease:
            fcntl.flock(lease, fcntl.LOCK_EX)
            observations = worker([fresh / "venvs/storyboard-vision/bin/python",
                                   args.frames / "src/storyboard_renderer/multi_review.py"], queries, limit=1200) if queries else []
        frames = [{"seconds": sec, "observed": text[:300]} for sec, text in
                  zip(range(0, seconds, interval), observations, strict=True)]
        persist(target / "sampled-observations.json", frames)
        timed_observation_packet(target, actual, brief, checks, audio, frames)
        packets.append((case.name, actual, target, brief, checks, indexed, audio, frames))

    with writer(args, args.models / model["file"], args.output / "judge.log") as endpoint:
        for name, actual, target, brief, checks, indexed, words, frames in packets:
            transcript = "".join(w["word"] for w in words)
            common = {**brief, "delivered_asr": transcript, "delivered_pixels": frames}
            for version, instructions, packet in (
                ("ordinary-observation", REVIEWERS["focus-is-relation-v5"] + " Return an exact heard quote for any failure.",
                 common),
                ("source-derived", DISCOVER, {**common, "checks": checks}),
                ("indexed-source", DISCOVER, {**common, "checks": indexed}),
            ):
                try:
                    result = ask(endpoint, instructions, packet, FIND, 650, target / f"{version}-response.json")
                except ValueError as error:
                    result = {"status": "uncertain", "defect": "", "quote": "", "why": str(error)}
                raw_status = result["status"]
                location = locate(result["quote"], words) if raw_status == "failed" else None
                if (raw_status == "failed" and not location) or (version != "ordinary-observation" and not packet["checks"]):
                    result["status"] = "uncertain"
                persist(target / f"{version}.json", {**result, "raw_status": raw_status, "interval": location,
                        "mp4_sha256": actual, "transcript_sha256": digest(words), "observations_sha256": digest(common)})


if __name__ == "__main__":
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packets", "output", "video", "frames"):
        parser.add_argument(name, type=Path)
    defaults = {"fresh": "ai/storyboard-rehearsal/fresh", "ffmpeg": "ai/tools/media/bin/ffmpeg",
                "models": "ai/storyboard-rehearsal/writer/models",
                "runtime": "ai/storyboard-rehearsal/writer/runtime/build/bin/llama-server",
                "lease": "ai/storyboard-build/v2/gpu.lock"}
    for name, value in defaults.items():
        parser.add_argument(f"--{name}", type=Path, default=home / value)
    parser.add_argument("--observations", type=Path, help="reuse prior same-MP4 observation packets")
    run(parser.parse_args())
