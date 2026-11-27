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
OPENING_NOT_ANSWER = (
    "A useful opening can deliberately leave the answer unresolved. If the question is clear and the first "
    "state provides the right focus, keeping the missing inputs unknown is expected. An early_reveal requires "
    "specific words or pixels that expose the correct answer or its embargoed evidence before the planned "
    "reveal. Never diagnose early_reveal because the answer is not yet possible to derive."
)
FOCUS_IS_RELATION = (
    "A comparison's focus can be the relationship between two objects. A speaker can direct attention with "
    "'this' if the corresponding object is visibly highlighted in that interval. Do not require that the "
    "viewer choose a winner before the reveal. Check the first intervals one at a time: use decoded_focus_mark "
    "when present, match the actually spoken reading, then check the question against the stated objective. "
    "This does not permit giving the answer early, using a wrong measurement, or covering up an incorrect "
    "spoken assertion. Preserve those independent failures."
)
PROMISE_BY_QUESTION = (
    "Do not require the first line or first highlight to state the entire teaching objective. For a comparison "
    "with an evidence-first opening, the first line must orient the viewer to its own visible observation; "
    "the later spoken question must clearly specify the comparison by the end of the opening. A cost or "
    "distance highlight on the line stating that cost or distance is correct. Do not require a highlighted "
    "question or mark this structure unclear solely because the question follows the observations. Still "
    "reject physical discrepancies and early answers with specific offered evidence."
)
REVIEWERS = {
    "observable-opening-v2": RUBRIC,
    "literal-evidence-v3": LITERAL_FIRST + " " + RUBRIC,
    "unanswered-is-valid-v4": OPENING_NOT_ANSWER + " " + LITERAL_FIRST + " " + RUBRIC,
    "focus-is-relation-v5": FOCUS_IS_RELATION + " " + LITERAL_FIRST + " " + RUBRIC,
    "promise-by-question-v6": PROMISE_BY_QUESTION + " " + FOCUS_IS_RELATION + " " + LITERAL_FIRST + " " + RUBRIC,
}
VERDICT = obj({"status": {"enum": ["accepted", "failed", "uncertain"]},
               "code": {"enum": ["ok", "unclear_focus", "wrong_value", "wrong_unit", "wrong_object", "early_reveal",
                                  "wrong_route", "illegible", "unsupported", "timing", "unobservable"]},
               "start_seconds": {"type": "number", "minimum": 0},
               "detail": {**TEXT, "maxLength": 420}, "repair": {"type": "string", "maxLength": 320}})


def heard_numbers(text):
    words = re.findall(r"\d+(?:\.\d+)?|[a-z]+", text.casefold())
    ones = dict(zip(("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                     "fifteen sixteen seventeen eighteen nineteen").split(), range(20), strict=True))
    tens = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10), strict=True))
    numbers = set()
    i = 0
    while i < len(words):
        word = words[i]
        if word == "one" and i and words[i-1] in ("this", "that", "which", "other"):
            i += 1
            continue
        if word[0].isdigit():
            numbers.add(float(word))
            i += 1
            continue
        value = 0
        if word in ones and 1 <= ones[word] <= 9 and words[i+1:i+2] == ["hundred"]:
            value = ones[word] * 100
            i += 2
            if words[i:i+1] == ["and"] and i+1 < len(words) and (words[i+1] in tens or words[i+1] in ones):
                i += 1
            word = words[i] if i < len(words) else ""
        if word in tens:
            value += tens[word]
            i += 1
            tail = ones.get(words[i], 0) if i < len(words) else 0
            if 1 <= tail <= 9:
                value += tail
                i += 1
            numbers.add(value)
        elif word in ones:
            numbers.add(value + ones[word])
            i += 1
        elif value:
            numbers.add(value)
        else:
            i += 1
    return numbers


def measured_quantities(text):
    """Corroborate narrow, unambiguous energy/power forms without dropping the unit."""
    words = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
             "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred and")
    numeric = r"(?:" + "|".join(words.split()) + r")\b"
    pattern = (r"(?<!\w)(?P<amount>\d+(?:\.\d+)?|" + numeric + r"(?:[ -]+" + numeric + r"){0,4})\s*"
               r"(?P<unit>kwh|kw|kilowatt[ -]hours?|kilowatts?)(?![a-z])")
    for match in re.finditer(pattern, text.casefold()):
        numbers = heard_numbers(match["amount"])
        if len(numbers) == 1:
            yield next(iter(numbers)), ("kWh" if "hour" in match["unit"] or match["unit"] == "kwh" else "kW")


def reading_number(probe):
    value = re.match(r"^\s*(\d+(?:\.\d+)?)\b", probe["display"])
    return float(value[1]) if value else None


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


def meter_faults(out, decoded, manifest, words, observed_focus=None):
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
        if observed_focus is not None:
            mark = focus_marks[0]
            observed_focus[cue["id"]] = {k: mark[k] for k in ("object", "label", "display")}
        end = decoded["cues"][index+1]["seconds"] if index+1 < len(decoded["cues"]) else decoded["duration"]
        heard = "".join(word["word"] for word in words if cue["seconds"] <= (word["start"]+word["end"])/2 < end)
        spoken = heard_numbers(heard)
        focused_values = set(measured_quantities(focus_marks[0]["display"]))
        spoken_values = set(measured_quantities(heard))
        if len(spoken_values) == 1:
            spoken = {number for number, _ in spoken_values}
        if len(focused_values) == 1 and len(spoken_values) == 1:
            observed_value, observed_unit = next(iter(spoken_values))
            expected_value, expected_unit = next(iter(focused_values))
            if observed_value == expected_value and observed_unit != expected_unit:
                faults.append({"status": "failed", "code": "wrong_unit", "start_seconds": cue["seconds"],
                               "detail": f"At this focus the audio says {observed_value:g} {observed_unit}, "
                                         f"but the reading is {expected_value:g} {expected_unit}.",
                               "repair": "Correct the spoken unit for this reading and recheck alignment."})
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
        elif not candidates and len(spoken_values) == 1 and reading_number(focus_marks[0]) is not None:
            faults.append({"status": "failed", "code": "wrong_value", "start_seconds": cue["seconds"],
                           "detail": f'The delivered audio says {number:g}, but no displayed reading of '
                                     f'{focus_marks[0]["label"]!r} has that value.',
                           "repair": "Reconcile the spoken value with the verified source and focused reading."})
    return faults


def review(args, brief, evidence, identity):
    from storygen import ROOT, read, writer

    out = args.out
    manifest, story = read(out / "manifest.json"), read(out / "story.json")
    lock = {"mp4_sha256": hashlib.sha256((out / "video.mp4").read_bytes()).hexdigest(),
            "manifest_sha256": digest(manifest), "configuration_sha256": digest(identity),
            "evidence_sha256": digest(evidence), "story_sha256": digest(story),
            "observation_version": "current-beat-frames/2"}
    existing = out / "local-opening-verdict.json"
    if existing.exists():
        cached = read(existing)
        if any(cached.get(k) != v for k, v in lock.items()):
            raise ValueError("opening review input changed")
        return cached
    decoded, words, _ = inspect_media(args, story, manifest)
    observed_focus = {}
    faults = meter_faults(out, decoded, manifest, words, observed_focus)
    persist(out / "decoded-meter-checks.json", faults)
    if faults:
        result = {**faults[0], **lock, "reviewer": "decoded-meter-probes/1"}
        persist(existing, result)
        return result
    starts = [cue["seconds"] for cue in decoded["cues"]]
    observations = visual_windows(args, story, manifest, decoded, include_previous=False)
    intervals = []
    for i, (start, observed) in enumerate(zip(starts, observations, strict=True)):
        end = starts[i+1] if i+1 < len(starts) else decoded["duration"]
        intervals.append({"start": start, "end": end, "pixels": observed, "frame_scope": "Current beat only",
                          "heard": "".join(w["word"] for w in words if start <= (w["start"]+w["end"])/2 < end),
                          "decoded_focus_mark": observed_focus.get(decoded["cues"][i]["id"]),
                          "frame_receipt": manifest["panels"][i].get("daily_visual", {}).get("route")})
    packet = {"objective": brief["objective"], "facts": brief.get("facts", []), "sources": evidence,
              "duration": decoded["duration"], "delivered": intervals}
    persist(out / "opening-review-packet.json", {**lock, **packet})
    model = read(ROOT / "models.json")["mistral-small"]
    with writer(args, args.models / model["file"], out / "opening-reviewer.log") as endpoint:
        instructions = REVIEWERS[identity["reviewer"]]
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
