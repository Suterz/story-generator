"""Adjudicate the actual muxed opening, keeping media evidence separate from expectations."""
import hashlib
import os
from pathlib import Path
import re
import subprocess

from daily import ask, obj, TEXT
from daily_evidence import digest, persist
from review_daily import inspect_media, visual_windows

RUBRIC = (
    "Review this 10–20 second educational opening. Each delivered row contains observations, not proof: inspect "
    "what the viewer hears and sees in the same interval. Accept when the spoken opening and first visible state "
    "make the focus and promise clear, evidence agrees with the brief, and no decisive answer is shown early. "
    "A real quantity on the wrong object is a defect; textual or spoken equivalents of the same value and unit "
    "are not defects. An opening need not answer the entire film. Reject a material defect only with the observed "
    "words or pixels and its timestamp, and propose the smallest plausible repair. If decisive evidence cannot "
    "be established, use uncertain. Do not invent a defect or infer audience retention."
)
LITERAL_FIRST = (
    "First read the delivered speech literally in order. If evidence gives a required reveal order, quote any "
    "later value that is already spoken in the forbidden interval. If the speech says a count 'instead of' "
    "another count, compare both counts to the brief; pictures of the correct end state cannot make wrong "
    "speech correct. Treat seeing an earlier state before a rewind as normal. Do not count a number that only "
    "appears in the brief as spoken. Then apply the rubric. Use the actual clip timeline, including excerpt offsets."
)
VERDICT = obj({"status": {"enum": ["accepted", "failed", "uncertain"]},
               "code": {"enum": ["ok", "unclear_focus", "wrong_value", "wrong_object", "early_reveal",
                                  "wrong_route", "illegible", "unsupported", "timing", "unobservable"]},
               "start_seconds": {"type": "number", "minimum": 0},
               "detail": {**TEXT, "maxLength": 420}, "repair": {"type": "string", "maxLength": 320}})


def heard_numbers(text):
    words = re.findall(r"\d+(?:\.\d+)?|[a-z]+", text.casefold())
    ones = dict(zip("one two three four five six seven eight nine".split(), range(1, 10), strict=True))
    tens = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10), strict=True))
    numbers = set()
    for i, word in enumerate(words):
        if word[0].isdigit():
            numbers.add(float(word))
        elif word in tens:
            numbers.add(tens[word] + (ones.get(words[i+1], 0) if i+1 < len(words) else 0))
    return numbers


def early_quantity(words, quantity, through, origin=0):
    """Detect a forbidden answer in delivered ASR, including split spoken numbers."""
    for i, row in enumerate(words):
        onset = row["start"] + origin
        if onset >= through:
            break
        text = row["word"].strip()
        tens = {"twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"}
        ones = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
        if text.casefold() in tens and i+1 < len(words):
            next_word = words[i+1]["word"].strip(" -.,!?").casefold()
            if next_word in ones:
                text += " " + next_word
        if quantity in heard_numbers(text):
            return {"status": "failed", "code": "early_reveal", "start_seconds": onset,
                    "detail": f"Delivered audio states {quantity:g} before the {through:g}s reveal boundary.",
                    "repair": "Move the answer to the permitted reveal or remove it from the opening."}
    return None


def meter_faults(out, decoded, manifest, words):
    """Check the focus mark in actual pixels, not only in the drawing request."""
    media = Path(os.getenv("DAILY_MEDIA", Path.home() / "ai/tools/media/bin"))
    indices = {frame: i for i, frame in enumerate(decoded["frames"], 1)}
    faults = []
    for index, (cue, panel) in enumerate(zip(decoded["cues"], manifest["panels"], strict=True)):
        probes = panel.get("daily_visual", {}).get("proof", {}).get("focus_probes", [])
        if not probes:
            continue
        png = out / f'phone/{indices[cue["frame"]]:03d}.png'
        pixels = subprocess.check_output([str(media / "ffmpeg"), "-v", "error", "-i", str(png),
                                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], timeout=20)
        if len(pixels) != 360*640*3:
            raise ValueError("decoded phone image has an unexpected size")
        focus_marks = []
        for probe in probes:
            x, y = probe["point"]
            pixel_index = (round(y*640)*360+round(x*360))*3
            r, g, b = pixels[pixel_index:pixel_index+3]
            focused = r >= 234 and 186 <= g <= 239 and 115 <= b <= 202
            if focused:
                focus_marks.append(probe)
            if focused != probe["focus"]:
                faults.append({"status": "failed", "code": "wrong_object", "start_seconds": cue["seconds"],
                               "detail": f'Decoded focus for {probe["object"]} / {probe["label"]} differs from the planned state.',
                               "repair": "Restore the intended focus state for that beat."})
        if len(focus_marks) != 1:
            continue
        end = decoded["cues"][index+1]["seconds"] if index+1 < len(decoded["cues"]) else decoded["duration"]
        spoken = heard_numbers("".join(word["word"] for word in words
                                        if cue["seconds"] <= (word["start"]+word["end"])/2 < end))
        if len(spoken) != 1:
            continue
        number = next(iter(spoken))
        candidates = [probe for probe in probes if (match := re.match(r"^\s*(\d+(?:\.\d+)?)\b", probe["display"]))
                      and float(match[1]) == number and probe["label"] == focus_marks[0]["label"]]
        if len(candidates) == 1 and candidates[0]["object"] != focus_marks[0]["object"]:
            correct = candidates[0]
            faults.append({"status": "failed", "code": "wrong_object", "start_seconds": cue["seconds"],
                           "detail": f'The delivered speech says {number:g}, but the highlight is on {focus_marks[0]["object"]}.',
                           "repair": f'Focus {correct["object"]} / {correct["label"]} in {cue["id"]}.',
                           "focus_edit": {"beat": cue["id"], "object": correct["object"], "label": correct["label"]}})
    return faults


def review(args, brief, evidence, identity):
    from storygen import ROOT, read, writer

    out = args.out
    manifest, story = read(out / "manifest.json"), read(out / "story.json")
    lock = {"mp4_sha256": hashlib.sha256((out / "video.mp4").read_bytes()).hexdigest(),
            "manifest_sha256": digest(manifest), "configuration_sha256": digest(identity),
            "evidence_sha256": digest(evidence), "story_sha256": digest(story)}
    existing = out / "local-opening-verdict.json"
    if existing.exists():
        cached = read(existing)
        if any(cached.get(k) != v for k, v in lock.items()):
            raise ValueError("opening review input changed")
        return cached
    decoded, words, _ = inspect_media(args, story, manifest)
    faults = meter_faults(out, decoded, manifest, words)
    persist(out / "decoded-meter-checks.json", faults)
    if faults:
        result = {**faults[0], **lock, "reviewer": "decoded-meter-probes/1"}
        persist(existing, result)
        return result
    observations = visual_windows(args, story, manifest, decoded)
    starts = [cue["seconds"] for cue in decoded["cues"]]
    intervals = []
    for i, (start, observed) in enumerate(zip(starts, observations, strict=True)):
        end = starts[i+1] if i+1 < len(starts) else decoded["duration"]
        intervals.append({"start": start, "end": end, "pixels": observed,
                          "heard": "".join(w["word"] for w in words if start <= (w["start"]+w["end"])/2 < end),
                          "frame_receipt": manifest["panels"][i].get("daily_visual", {}).get("route")})
    packet = {"objective": brief["objective"], "facts": brief.get("facts", []), "sources": evidence,
              "duration": decoded["duration"], "delivered": intervals}
    persist(out / "opening-review-packet.json", {**lock, **packet})
    model = read(ROOT / "models.json")["mistral-small"]
    with writer(args, args.models / model["file"], out / "opening-reviewer.log") as endpoint:
        instructions = (LITERAL_FIRST + " " + RUBRIC if identity["reviewer"] == "literal-evidence-v3" else RUBRIC)
        result = ask(endpoint, instructions, packet, VERDICT, 620, out / "opening-review-response.json")
    if (result["status"] == "accepted") != (result["code"] == "ok"):
        raise ValueError("reviewer status and defect disagree")
    if result["start_seconds"] > decoded["duration"]:
        raise ValueError("reviewer cited time outside the exported clip")
    if result["status"] == "accepted":
        result["repair"] = ""
    final = {**result, **lock, "reviewer_sha256": model["sha256"]}
    persist(existing, final)
    return final
