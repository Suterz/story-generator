"""Run an explicitly scoped, exact daily/3 lesson through the ordinary renderer."""
from fractions import Fraction
import fcntl
import hashlib
import re
import subprocess
from urllib.error import URLError

from .readiness import inspect, plan_errors, stages
from daily_evidence import digest, persist
from opening_bindings import spoken_integer


def plan_comparison(brief):
    """Compile the supported two-object teaching pattern from facts, not prose guesses."""
    comparison = brief["comparison"]
    if comparison["unit"] != "kWh" or len(brief["mechanism"]) != 1:
        raise ValueError("the deployed exact comparison supports kWh and one worked-ratio phase")
    objects = comparison["objects"]
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z ]{0,18}", r["name"]) for r in objects):
        raise ValueError("comparison names need short pronounceable labels")
    if any(max(obj["input"], obj["returned"]) >= 1000 for obj in objects):
        raise ValueError("reading exceeds the supported spoken integer range")
    ratios = [Fraction(int(obj["returned"]), int(obj["input"])) * 100 for obj in objects]
    if any(p.denominator != 1 or not 0 <= p <= 100 for p in ratios):
        raise ValueError("comparison needs whole-percent returns between zero and one hundred")
    values = [int(ratio) for ratio in ratios]
    phase = stages(brief)
    schedule = [{"id": s["id"], "establishes": s["establishes"]} for s in phase]
    if errors := plan_errors(brief, schedule):
        raise ValueError("; ".join(errors))
    if "ratios_shown" not in phase[2]["establishes"] or "inputs_revealed" not in phase[1]["establishes"]:
        raise ValueError("worked ratio must establish ratios_shown, and the lesson must establish inputs_revealed")
    spoken = spoken_integer
    a, b = objects
    transfer = brief["transfer"]
    transfer_input = spoken(int(transfer["input"]))
    transfer_return = spoken(int(transfer["returned"]))
    transfer_percent = spoken(int(transfer["percent"])).capitalize()
    title = "Which made better use of its input?"
    outcome = ("Both returned the same share of their input." if comparison["answer"] == "tie" else
               f"{comparison['answer']} made better use of its input.")
    # The argument order is executable: focus two returns, reveal inputs, show
    # both computed ratios, and only then allow the conclusion and transfer.
    beats = [
        (0, f"{a['name']} returns {spoken(a['returned'])} kilowatt-hours.", False, False, 0),
        (0, f"{b['name']} returns {spoken(b['returned'])} kilowatt-hours. {title}", False, False, 1),
        (1, f"Look at the inputs. {a['name']} takes in {spoken(a['input'])}; "
            f"{b['name']} takes in {spoken(b['input'])} kilowatt-hours.", True, False, None),
        (2, "Divide each return by its own input. "
            f"{a['name']} returns {spoken(values[0])} percent. "
            f"{b['name']} returns {spoken(values[1])} percent.", True, True, None),
        (3, f"Now compare the shares. {outcome}", True, True, None),
        (3, f"A third battery takes in {transfer_input} and returns {transfer_return} kilowatt-hours. "
            "What share is that?", True, True, None),
        (3, f"{transfer_percent} percent. Divide {transfer_return} by {transfer_input}.", True, True, None),
    ]
    return schedule, beats, values


def compile_lesson(brief, voice):
    schedule, data, ratios = plan_comparison(brief)
    phase = stages(brief)
    script, beats, starts = [], [], []
    for i, (stage, narration, inputs, result, focus) in enumerate(data):
        id_ = f"lesson-{i+1}"
        if i in (0, 2):
            starts.append(id_)
        script.append({"id": id_, "text": narration, "caption": narration})
        meters = []
        for index, obj in enumerate(brief["comparison"]["objects"]):
            fields = [{"label": "Energy returned", "display": f'{obj["returned"]} kWh', "focus": focus == index},
                      {"label": "Energy put in", "display": f'{obj["input"]} kWh' if inputs else "?", "focus": False}]
            if result:
                fields.append({"label": "Share returned", "display": f'{obj["returned"]}/{obj["input"]} = {ratios[index]}%',
                               "focus": False})
            meters.append({"object": obj["name"], "readings": fields})
        beats.append({"id": id_, "cue": ({"ms": 0} if not i else
                      {"utterance_id": id_, "phrase": " ".join(narration.split()[:3]), "occurrence": 1}),
                      "panel": {"op": "new_scene", "scene_id": id_, "objective": phase[stage]["description"],
                                "instruction": phase[stage]["must_show"], "retry_budget": 0,
                                "daily": {"kind": "exact", "data": {"operation": "meters", "meters": meters},
                                          "claims": phase[stage]["evidence_ids"], "obligations": [{"id": phase[stage]["id"]}],
                                          "route_reason": "Source-bound measurements and sequential ratio proof."}}})
    duration = brief["duration"]
    minimum = duration["min_seconds"] if duration["kind"] == "hard" else 20
    maximum = duration["max_seconds"] if duration["kind"] == "hard" else 300
    return {"title": brief["topic"], "visual": {"story_context": brief["objective"],
            "visual_signature": "Portrait educational schematic on light paper", "graphic_theme": "paper"},
            "script": script, "beats": beats, "chapter_starts": starts, "voice_profile": voice,
            "lesson_contract": "daily/3", "min_ms": minimum*1000, "max_ms": maximum*1000}, schedule


def verify_order(brief, decoded, audio, manifest):
    """Verify the computed result is in the delivered diagram before the spoken conclusion."""
    faults = []
    for index, panel in enumerate(manifest["panels"][:3]):
        inputs = [row for meter in panel.get("daily_visual", {}).get("proof", {}).get("meters", [])
                  for row in meter["readings"]]
        if any(row["label"] == "Share returned" for row in inputs):
            faults.append({"detail": f"Worked ratios appear before the proof cue in panel {index+1}"})
        if index < 2 and any(row["label"] == "Energy put in" and row["display"] != "?" for row in inputs):
            faults.append({"detail": f"An input was disclosed before the opening question in panel {index+1}"})
    proof = manifest["panels"][3].get("daily_visual", {}).get("proof", {})
    meters = proof.get("meters", [])
    for obj, meter in zip(brief["comparison"]["objects"], meters):
        percentage = Fraction(int(obj["returned"]), int(obj["input"])) * 100
        expected = f'{obj["returned"]}/{obj["input"]} = {percentage}%'
        if meter["object"] != obj["name"] or not any(
                row["label"] == "Share returned" and row["display"] == expected for row in meter["readings"]):
            faults.append({"detail": f"Missing worked fraction for {obj['name']}"})
    if len(meters) != 2:
        faults.append({"detail": "Missing two worked ratios in rendered panel receipt"})
    proof_start = decoded["cues"][3]["seconds"]
    conclusion_start = decoded["cues"][4]["seconds"]
    if not proof_start < conclusion_start:
        faults.append({"detail": "The worked result must precede the conclusion"})
    early = " ".join(word["word"].strip() for word in audio if word["end"] < conclusion_start)
    early = re.sub(r"\s+", " ", early.casefold())
    # The hook asks "Which made better use …?" using the same words as the
    # answer. Only a conclusion with an actual subject is a reveal.
    winner = brief["comparison"]["answer"]
    statement = (r"\bboth returned the same share\b" if winner == "tie" else
                 rf"\b{re.escape(winner.casefold())} made better use of its input\b")
    alternatives = [rf"\b{re.escape(row['name'].casefold())} made better use of its input\b"
                    for row in brief["comparison"]["objects"]]
    alternatives.append(r"\bboth returned the same share\b")
    if any(re.search(candidate, early) for candidate in alternatives):
        faults.append({"detail": "Delivered audio declares the result before the conclusion cue"})
    end = decoded["cues"][5]["seconds"] if len(decoded["cues"]) > 5 else float("inf")
    actual = " ".join(word["word"].strip() for word in audio
                      if conclusion_start <= (word.get("start", word["end"])+word["end"])/2 < end)
    if not re.search(statement, re.sub(r"\s+", " ", actual.casefold())):
        faults.append({"detail": "The expected conclusion is not corroborated in the delivered result interval"})
    return faults


def verify_transfer(brief, decoded, audio):
    """Corroborate the changed operands and answer using the exported speech."""
    transfer = brief["transfer"]
    cues = {cue["id"]: cue["seconds"] for cue in decoded["cues"]}
    question, answer = cues["lesson-6"], cues["lesson-7"]

    def amount(key):
        value = int(transfer[key])
        words = re.escape(spoken_integer(value)).replace(r"\-", r"[- ]").replace(r"\ ", r"[\s-]+")
        return rf"\b(?:{value}|{words})(?!\d|\.\d)"

    def spoken_between(start, end):
        return " ".join(row["word"].strip().casefold() for row in audio
                        if start <= (row["start"] + row["end"]) / 2 < end)

    input_, returned, rate = map(amount, ("input", "returned", "percent"))
    question_text = spoken_between(question - .65, answer)
    answer_text = spoken_between(answer - .65, decoded["duration"])
    faults = []
    if not re.search(rf"\btakes in {input_}\W+and returns {returned}\s*(?:kwh|kilowatt[- ]hours?)\b",
                     question_text):
        faults.append({"start_seconds": question, "detail": "Changed input and return were not corroborated in the delivered question"})
    percent = rf"{rate}\s*(?:%|percent\b)"
    division = rf"(?:\bdivide {returned} by {input_}|{returned} divided by {input_})\b"
    if not re.search(rf"{percent}[\s.,:]+{division}", answer_text):
        faults.append({"start_seconds": answer, "detail": "Expected percentage and division were not corroborated in the delivered answer"})
    return faults


def observe_ratio_panel(args, decoded, brief):
    """Ask the pinned vision model to read the actual proof frame, without the answers."""
    import os
    from pathlib import Path

    from review_daily import worker

    runtime = Path(os.getenv("DAILY_RUNTIME_ROOT", Path.home() / "ai/storyboard-rehearsal/fresh"))
    frames = getattr(args, "frames_repo", None)
    if frames is None:
        frames = Path(os.environ["DAILY_FRAMES_REPO"])
    proof_frame = decoded["cues"][3]["frame"]
    index = decoded["frames"].index(proof_frame) + 1
    image = args.out / f"phone/{index:03d}.png"
    query = {"images": [[f"Phone frame {proof_frame}", str(image)]],
             "prompt": "Transcribe the two battery names and each division expression including its percent. "
                       "Use only text you can actually see in the two cards, above the caption."}
    with args.lease.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        observed, = worker([runtime / "venvs/storyboard-vision/bin/python",
                            frames / "src/storyboard_renderer/multi_review.py"], [query], limit=300)
    confirmed = []
    for item in brief["comparison"]["objects"]:
        value = Fraction(int(item["returned"]), int(item["input"])) * 100
        phrase = f'{item["returned"]}/{item["input"]}={value}%'
        lines = observed.casefold().replace("÷", "/").splitlines()
        matches = [line for line in lines if item["name"].casefold() in line and phrase in re.sub(r"\s+", "", line)]
        confirmed.append(bool(matches))
    return {"observed": observed, "frame": proof_frame, "both_equations_transcribed": all(confirmed)}


def run(args):
    from pathlib import Path
    import os

    from review_daily import inspect_media
    from opening_review import meter_faults
    from storygen import read, render, validate_native

    out = args.out
    brief = read(args.input)
    receipt = inspect(brief)
    pin = os.getenv("DAILY_FREEZE")
    identity = {**receipt, "voice": args.voice, "endpoint": args.video_url,
                "freeze_sha256": hashlib.sha256(Path(pin).read_bytes()).hexdigest() if pin else None}
    lock = out / "brief-readiness.json"
    if lock.exists() and read(lock) != identity:
        raise ValueError("changed brief or execution pin; use a new output directory")
    persist(lock, identity)
    final = out / "terminal-outcome.json"
    if final.exists():
        print(final.read_text(), end="")
        return
    outcome = {"status": receipt["status"], "issues": receipt["issues"], "brief_sha256": digest(brief),
               "render_submitted": False}
    if receipt["status"] == "ready":
        if not receipt.get("queueable"):
            outcome.update(status="withhold", reason="ready brief; no supported execution route for this teaching pattern")
        elif not pin:
            outcome.update(status="withhold", reason="no development or release configuration receipt")
        elif not (os.getenv("STORYGEN_VALIDATOR_PYTHON") and os.getenv("STORYGEN_RENDERER_SOURCES")):
            outcome.update(status="withhold", reason="production brief needs native renderer preflight")
        else:
            try:
                story, plan = compile_lesson(brief, args.voice)
                validate_native(story)
                persist(out / "story.json", story)
                persist(out / "teaching-plan.json", plan)
                result = render(args, story)
                outcome.update(render_submitted=True, renderer=result)
                if result["state"] != "succeeded":
                    outcome.update(status="withhold", reason=result.get("error", result["state"]))
                else:
                    manifest = read(out / "manifest.json")
                    decoded, audio, _ = inspect_media(args, story, manifest)
                    marks = {}
                    faults = (meter_faults(out, decoded, manifest, audio, marks)
                              + verify_order(brief, decoded, audio, manifest)
                              + verify_transfer(brief, decoded, audio))
                    actual = decoded["duration"]
                    target = brief["duration"]
                    proof = {"faults": faults, "focus": marks, "mp4_sha256": decoded["video_sha256"],
                             "duration_seconds": actual, "configuration_sha256": digest(identity),
                             "duration_preference_met": target["min_seconds"] <= actual <= target["max_seconds"],
                             "worked_ratio_cue_seconds": decoded["cues"][3]["seconds"],
                             "conclusion_cue_seconds": decoded["cues"][4]["seconds"]}
                    if not faults:
                        proof["decoded_ratio_observation"] = observe_ratio_panel(args, decoded, brief)
                        if not proof["decoded_ratio_observation"]["both_equations_transcribed"]:
                            faults.append({"detail": "the actual proof frame could not be verified for both objects"})
                    persist(out / "exact-review.json", proof)
                    outcome.update(status="withhold" if faults else "draft_ready",
                                   reason=faults[0]["detail"] if faults else "exact checks passed; independent editorial quality unqualified",
                                   mp4_sha256=proof["mp4_sha256"])
            except (ValueError, RuntimeError, OSError, KeyError, URLError, subprocess.SubprocessError) as error:
                outcome.update(status="withhold", reason=str(error), render_submitted=(out / "submission.json").exists())
    persist(out / "first-outcome.json", outcome)
    persist(final, outcome)
    print(final.read_text(), end="")
