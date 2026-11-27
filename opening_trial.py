"""Render and review versioned daily/2 opening experiments."""
import hashlib
import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator

from daily import DAILY_OUTLINE, SECTION, adapt, array, ask, collect, extract_claims, INTENT, obj, TEXT
from daily_evidence import digest, persist

BASELINE = ("Plan three or four chapters for this portrait explanation. Teach in evidence order. "
            "Give a distinct one-sentence goal of at most twelve words per chapter. Use four chapters "
            "when the brief asks for at least three minutes. Open directly on a picture that poses the question. "
            "If the comparison depends on readings, positions or relationships, choose a schematic with the opening "
            "evidence visible at phone size; a generic illustration does not establish the comparison. "
            "Choose a visual for the evidence: exact for quantities and persistent objects, authentic for real "
            "items whose appearance matters, illustration when appearance may vary. Return only the requested JSON.")
VISIBLE_QUESTION = (
    "Design a fifteen-second portrait opening. Choose a puzzle, observation, prediction, or direct promise. "
    "The first spoken line must direct attention to evidence already on the screen. Make it clear what the "
    "viewer can and cannot infer yet, and let the question land before exposing its answer. "
    "Generate one progressive scene with three or four states, roughly 30–40 spoken words in total. "
    "Write spoken numbers as words and use digits in labels. For an exact comparison, use the same two objects "
    "in every state. With the meters operation, show a reading in its own focus state on the sentence speaking "
    "it; missing readings may be '?'. Use exact drawings for essential measurements, authentic imagery only "
    "when it is actual evidence, and illustration only if appearance can vary. "
    "Do not add data. In the last sentence preview the next observation without giving away the answer. "
    "Use short, natural sentences."
)
QUESTION_BEFORE_ANSWER = (
    "Create an opening, not a summary of the answer. Start by making one observable contrast. Then ask one "
    "question whose answer the viewer cannot yet see. Finish with a clue about what to inspect next. "
    "For a numerical prediction, decide which readings would give away the answer; render those readings as '?' "
    "in ALL opening states. Do not narrate their values, the calculation, or the winner. "
    "For a two-object quantitative comparison use exact meters, not a generic image. Keep the same objects; "
    "focus only the reading named in that short line. Put the viewer's question in its own state. "
    "Speak quantities and units in full words, never digits or abbreviations. "
    "For a nonnumerical topic, use the actual object or exact relationship when it is the evidence; "
    "use local artwork when it is only illustrative. Ask what makes the observation surprising."
)
SHORT_LINES = " Make each narration field one sentence of seven to ten words. Four short lines, not paragraphs."
PROMISE_SPEC = (
    "Choose a good opening for this viewer. Write one short spoken question or promise. Specify what evidence "
    "must be visible before it and the answer or evidence that belongs AFTER the opening. Choose a prediction "
    "only if viewers can make a fair guess. Do not teach the answer yet."
)
LOCKED_PROMISE = (" Use the locked promise verbatim in a spoken line. All states occur before the answer. "
                  "Do not put the withheld evidence into narration, captions, titles or drawings.")
LITERAL_EMBARGO = (" The withheld array contains actual numeric magnitudes from supplied facts, not IDs, sequence "
                   "numbers, placeholder numbers or counters. For example, if you need a value of 120 to answer "
                   "the question, put 120 there and describe its field as hidden in visible_now. Leave the array "
                   "empty if the reveal has no supplied numeric magnitude.")
VISIBLE_SPLIT = (" Describe visible_now using only the immediate evidence. Include at least one useful observation "
                 "rather than hiding everything. Any unknown reading named there must be shown as a question mark, "
                 "not its value. A value cannot be both visible and withheld.")
EXECUTE = ("Write one short opening chapter, three or four visual states, roughly 30–40 spoken words in total. "
           "Write spoken numbers as words and use digits in labels. "
           'visual_data for exact is {"operation":"meters","meters":[{"object":"name","readings":'
           '[{"label":"label","display":"? or value with unit","focus":false}]}]} with two objects, '
           'or {"operation":"bars","unit":"unit","rows":[["label",1],["other",2]]}; '
           'for authentic use {"subject":"public search description"}; for illustration use {}. '
           "Set claim_ids to applicable approved keys. Use [] for obligation_ids; the preview binds them.")
SCENE = obj({**SECTION["properties"], "kind": {"enum": ["exact", "authentic", "illustration"]},
             "route_reason": {**TEXT, "maxLength": 180}},
            ["narration", "visible", "claim_ids", "visual_data", "kind"])
OPEN = obj({"promise": {**TEXT, "maxLength": 120}, "states": array(SCENE, 3, 4)})
PROMISE = obj({"line": {**TEXT, "maxLength": 85}, "visible_now": {**TEXT, "maxLength": 180},
               "withheld": array({"type": "number"}, maximum=5), "why_wait": {**TEXT, "maxLength": 170}})
STABLE_COMPARISON = (
    "Make a four-line opening, not a summary. The brief compares two objects with measured readings. "
    "Choose one comparable reading from each object which the viewer may see now, and name the other reading "
    "they would need to answer the question. Do not output either hidden value in narration or labels. "
    "The first line refers to the first given reading, the second to the second reading, the third asks the "
    "question, and the fourth asks the viewer to look for the missing evidence. Each line is one short sentence, "
    "five to nine words, 24 to 34 words total. Speak numbers and units in words. Use digits for the visible "
    "reading labels. Output facts from the supplied evidence only. Put the actual spoken question in lines[2]."
)
SAME_PROPERTY = (" Compare the same measured property for both objects. Use the same measurement verb in "
                 "lines one and two: for example, both measurements can be travel distance, but one "
                 "distance and one duration are not comparable. known_label and missing_label name measured "
                 "properties, not objects. Each line shares the same exact unit where numeric.")
COMPARISON = obj({"objects": array(obj({"label": {**TEXT, "maxLength": 25},
                                       "reading": {**TEXT, "maxLength": 22}}), 2, 2),
                  "known_label": {**TEXT, "maxLength": 23}, "missing_label": {**TEXT, "maxLength": 23},
                  "lines": array({**TEXT, "maxLength": 90}, 4, 4)})


def comparison_plan(value, approved, *, same_property=False):
    import re
    from opening_review import heard_numbers

    if not value["lines"][2].endswith("?"):
        raise ValueError("comparison does not ask a spoken question")
    count = sum(len(line.split()) for line in value["lines"])
    if not 24 <= count <= 37:
        raise ValueError(f"comparison opening has {count} words; use 24–37")
    if value["known_label"].casefold() == value["missing_label"].casefold():
        raise ValueError("comparison uses the same label for known and missing values")
    names = [item["label"] for item in value["objects"]]
    if len(set(names)) != 2:
        raise ValueError("comparison requires two distinct objects")
    if same_property:
        import string

        names = {name.casefold().strip() for name in names}
        if any(value[key].casefold().strip() in names for key in ("known_label", "missing_label")):
            raise ValueError("opening meter label names the object instead of the measured property")
        motions = {"returns", "takes", "uses", "receives", "outputs", "travels", "lasts", "weighs", "costs"}
        verbs = [set(line.casefold().translate(str.maketrans("", "", string.punctuation)).split()) & motions
                 for line in value["lines"][:2]]
        if all(verbs) and verbs[0].isdisjoint(verbs[1]):
            raise ValueError("opening lines use different measurement verbs")
    for item, line in zip(value["objects"], value["lines"][:2], strict=True):
        reading = re.match(r"^\s*(\d+(?:\.\d+)?)\b", item["reading"])
        if not reading or heard_numbers(line) != {float(reading[1])}:
            raise ValueError("spoken opening does not identify each displayed numeric reading")
    return {"promise": value["lines"][2], "states": [
        {"narration": line, "visible": "The same two objects, with known readings and the missing readings hidden.",
         "kind": "exact", "claim_ids": sorted(approved),
         "route_reason": "The question depends on exact readings paired with persistent objects.",
         "visual_data": {"operation": "meters", "meters": [
             {"object": item["label"], "readings": [
                 {"label": value["known_label"], "display": item["reading"], "focus": index == row},
                 {"label": value["missing_label"], "display": "?", "focus": False}]}
             for row, item in enumerate(value["objects"])]}}
        for index, line in enumerate(value["lines"])]}


def guard_promise(plan, lock):
    import re
    from opening_review import heard_numbers

    promise = lock["line"].strip()
    spoken = " ".join(s["narration"] for s in plan["states"])
    if promise.casefold() not in spoken.casefold():
        raise ValueError("opening omitted its locked spoken promise")
    embargoed = set(lock["withheld"])
    if embargoed & heard_numbers(spoken):
        raise ValueError("opening narration includes an embargoed quantity")
    for state in plan["states"]:
        data = state["visual_data"]
        visible = [r["display"] for m in data.get("meters", []) for r in m["readings"]]
        visible += [str(row[1]) for row in data.get("rows", [])]
        numbers = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", " ".join(visible))}
        if embargoed & numbers:
            raise ValueError("opening image includes an embargoed quantity")


def check_embargo(spec, facts, *, check_visible=False):
    import re

    def numbers(text):
        return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)}

    reported = numbers(" ".join(facts))
    if set(spec["withheld"]) - reported:
        raise ValueError("opening embargo uses values not present in supplied facts")
    if check_visible and set(spec["withheld"]) & numbers(spec.get("visible_now", "")):
        raise ValueError("opening promise both displays and withholds the same quantity")


def compile_preview(brief, plan, approved, voice):
    from storygen import SIGNATURES, words

    script, beats = [], []
    for i, section in enumerate(plan["states"], 1):
        key = f"opening-{i}"
        if not set(section["claim_ids"]) <= approved:
            raise ValueError(f"{key}: unsupported claim ID")
        narration = section["narration"]
        # Choose whole authored words before tokenization expands compounds.
        cue = " ".join(narration.split()[:3])
        if len(words(cue)) < 2:
            raise ValueError(f"{key}: no usable spoken cue")
        script.append({"id": key, "text": narration, "caption": narration})
        beats.append({"id": key, "cue": {"ms": 0} if i == 1 else {"utterance_id": key, "phrase": cue},
                      "panel": {"op": "new_scene", "scene_id": key, "objective": plan["promise"],
                                "instruction": section["visible"], "retry_budget": 0,
                                "daily": {"kind": section["kind"], "data": section["visual_data"],
                                          "claims": section["claim_ids"], "obligations": [{"id": key}],
                                          "route_reason": section.get("route_reason", section["visible"])}}})
    signature = brief.get("signature", "paper")
    return {"title": brief["topic"], "visual": {"story_context": brief["objective"],
            "visual_signature": SIGNATURES.get(signature, signature), "graphic_theme": "paper"},
            "script": script, "beats": beats, "chapter_starts": [script[0]["id"]], "voice_profile": voice,
            "opening_preview": True}


def study(args, root, out, story, result):
    """Expose the same observable facts for early stops and delivered clips."""
    report = {"outcome": result["status"], "diagnosis": result["code"], "renderer_submitted":
              (out / "submission.json").exists()}
    if story:
        report["route_sequence"] = [b["panel"]["daily"]["kind"] for b in story["beats"]]
        report["captioned_utterances"] = sum(bool(row.get("caption")) for row in story["script"])
        report["authored_words"] = sum(len(row["text"].split()) for row in story["script"])
    if (out / "decoded-review.json").exists():
        decoded = json.loads((out / "decoded-review.json").read_text())
        report.update(duration_seconds=decoded["duration"], cues=decoded["cues"])
    if (out / "manifest.json").exists():
        manifest = json.loads((out / "manifest.json").read_text())
        report["panel_hashes"] = [panel["sha256"] for panel in manifest["panels"]]
    receipt = root / "retrieval.json"
    report["source_requests"] = (sum(event.get("requests") or 0 for event in json.loads(receipt.read_text()))
                                 if receipt.exists() else None)
    persist(out / "measurements.json", report)


def repair_focus(story, edit):
    beat = next(beat for beat in story["beats"] if beat["id"] == edit["beat"])
    meters = beat["panel"]["daily"]["data"]["meters"]
    matched = 0
    for meter in meters:
        for reading in meter["readings"]:
            reading["focus"] = meter["object"] == edit["object"] and reading["label"] == edit["label"]
            matched += reading["focus"]
    if matched != 1:
        raise ValueError("focus repair did not address exactly one reading")
    return story


def run_opening(args):
    from argparse import Namespace
    from storygen import ROOT, read, render, validate_native, writer
    from opening_review import review
    from urllib.error import URLError
    import subprocess
    from datetime import datetime, timezone

    root = args.out
    first = root / "first-outcome.json"
    terminal = root / "terminal-outcome.json"
    brief = adapt(read(args.input), args.daily)
    freeze = Path(os.environ["DAILY_FREEZE"])
    identity = {"schema": "opening-experiment/1", "brief": hashlib.sha256(args.input.read_bytes()).hexdigest(),
                "freeze_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(), "voice": args.voice,
                "writer": args.opening_preview, "reviewer": args.opening_reviewer, "budget": 1,
                "writer_weights": read(ROOT / "models.json")[args.model]["sha256"],
                       "endpoint": args.video_url, "seed": 437,
                       "instruction_sha256": hashlib.sha256(
                           {"baseline-v1": BASELINE + EXECUTE, "visible-question-v2": VISIBLE_QUESTION + EXECUTE,
                            "question-before-answer-v3": QUESTION_BEFORE_ANSWER + EXECUTE,
                            "short-question-v4": QUESTION_BEFORE_ANSWER + SHORT_LINES + EXECUTE,
                            "locked-promise-v5": PROMISE_SPEC + QUESTION_BEFORE_ANSWER + SHORT_LINES + LOCKED_PROMISE + EXECUTE,
                            "literal-embargo-v6": PROMISE_SPEC + LITERAL_EMBARGO + QUESTION_BEFORE_ANSWER
                            + SHORT_LINES + LOCKED_PROMISE + EXECUTE,
                            "visible-split-v7": PROMISE_SPEC + LITERAL_EMBARGO + VISIBLE_SPLIT + QUESTION_BEFORE_ANSWER
                            + SHORT_LINES + LOCKED_PROMISE + EXECUTE,
                            "stable-comparison-v8": STABLE_COMPARISON,
                            "same-property-v9": STABLE_COMPARISON + SAME_PROPERTY}
                           [args.opening_preview].encode()).hexdigest()}
    if args.voice.startswith("drama3-") and args.video_repo:
        registry = args.video_repo / "voices/drama3/narrators.json"
        profile = read(registry)
        identity["narrator"] = profile["narrators"][args.voice[-1]]["sha256"]
        identity["voice_registry_sha256"] = hashlib.sha256(registry.read_bytes()).hexdigest()
    path = root / "input-lock.json"
    if path.exists() and read(path) != identity:
        raise ValueError("opening experiment inputs changed")
    persist(path, identity)
    if terminal.exists():
        print(terminal.read_text(), end="")
        return
    model = args.models / read(ROOT / "models.json")[args.model]["file"]
    facts = brief.get("facts", [])
    previous = None
    for i in range(2):
        out = root / f"attempt-{i+1:02d}"
        out.mkdir(exist_ok=True)
        args_here = Namespace(**{**vars(args), "out": out})
        story = None
        try:
            cached = out / "opening-outcome.json"
            if cached.exists():
                result = read(cached)
                if i == 0 and not first.exists():
                    persist(first, {**identity, **result})
                if result["status"] == "accepted" or not result.get("repair"):
                    break
                previous = result
                continue
            if not (root / "evidence.json").exists():
                with writer(args, model, root / "intent.log") as endpoint:
                    intent = ask(endpoint, "Identify indispensable factual claims and their zero-based supporting "
                                 "caller fact indices. Group related facts; do not invent facts or duplicates.",
                                 brief, INTENT, 850, root / "intent-response.json")
                claims = extract_claims(intent, facts)
                ledger = collect(Namespace(**{**vars(args), "out": root}), {"claims": claims},
                                 model, datetime.now(timezone.utc).date())
                persist(root / "evidence.json", ledger)
            ledger = read(root / "evidence.json")
            missing = [row for row in ledger.values() if row["essential"] and not row["approved"]]
            if missing:
                row = missing[0]
                raise ValueError(f'essential claim {row["claim"]!r}: {row["route"]}')
            approved = {key: {"claim": row["claim"], "passages": [s["passage"] for s in row["approved"]]}
                        for key, row in ledger.items() if row["approved"]}
            if previous and previous.get("focus_edit") and not (out / "story.json").exists():
                story = repair_focus(read(root / "attempt-01/story.json"), previous["focus_edit"])
                persist(out / "repair.json", previous["focus_edit"])
                persist(out / "story.json", validate_native(story))
            if not (out / "story.json").exists():
                packet = {**brief, "approved": approved}
                if previous:
                    packet["repair"] = previous
                    packet["previous_plan"] = read(root / "attempt-01/plan.json")
                with writer(args, model, out / "opening.log") as endpoint:
                    structured = args.opening_preview in ("stable-comparison-v8", "same-property-v9")
                    if structured:
                        same = args.opening_preview == "same-property-v9"
                        instruction = STABLE_COMPARISON + (SAME_PROPERTY if same else "")
                        state = ask(endpoint, instruction, packet, COMPARISON, 850,
                                    out / "comparison-response.json")
                        persist(out / "comparison.json", state)
                        try:
                            plan = comparison_plan(state, approved, same_property=same)
                        except ValueError as error:
                            result = {"status": "withheld", "code": "plan_guard", "detail": str(error),
                                      "repair": "Apply the opening size and contrast rules."}
                            persist(out / "plan.json", state)
                            persist(out / "opening-outcome.json", result)
                            if i == 0:
                                persist(first, {**identity, **result})
                                previous = result
                                continue
                            break
                    elif args.opening_preview == "baseline-v1":
                        outline = ask(endpoint, BASELINE, packet, DAILY_OUTLINE, 1250, out / "outline-response.json")
                        packet["outline"] = outline
                        instruction = "Follow the proposed opening. " + EXECUTE
                    else:
                        selected = VISIBLE_QUESTION if args.opening_preview == "visible-question-v2" else QUESTION_BEFORE_ANSWER
                        if args.opening_preview not in ("baseline-v1", "visible-question-v2", "question-before-answer-v3"):
                            selected += SHORT_LINES
                        if args.opening_preview in ("locked-promise-v5", "literal-embargo-v6", "visible-split-v7"):
                            spec = root / "promise.json"
                            if not spec.exists():
                                instructions = PROMISE_SPEC
                                if args.opening_preview != "locked-promise-v5":
                                    instructions += LITERAL_EMBARGO
                                if args.opening_preview == "visible-split-v7":
                                    instructions += VISIBLE_SPLIT
                                candidate = ask(endpoint, instructions, packet, PROMISE, 450, root / "promise-response.json")
                                if args.opening_preview != "locked-promise-v5":
                                    source_passages = [passage for row in approved.values() for passage in row["passages"]]
                                    check_embargo(candidate, source_passages, check_visible=args.opening_preview == "visible-split-v7")
                                persist(spec, candidate)
                            packet["locked_promise"] = read(spec)
                            selected += LOCKED_PROMISE
                        instruction = selected + " " + EXECUTE
                    if not structured:
                        if previous:
                            instruction += " Repair only the specific observed defect and preserve the supported facts."
                        plan = ask(endpoint, instruction, packet, OPEN, 2000, out / "plan-response.json")
                persist(out / "plan.json", plan)
                if args.opening_preview in ("locked-promise-v5", "literal-embargo-v6", "visible-split-v7"):
                    try:
                        guard_promise(plan, packet["locked_promise"])
                    except ValueError as error:
                        result = {"status": "withheld", "code": "plan_guard", "detail": str(error),
                                  "repair": "Keep the locked spoken promise and remove the information embargo breach."}
                        persist(out / "opening-outcome.json", result)
                        if i == 0:
                            persist(first, {**identity, **result})
                            previous = result
                            continue
                        break
                story = validate_native(compile_preview(brief, plan, set(approved), args.voice))
                persist(out / "story.json", story)
            story = read(out / "story.json")
            render_result = render(args_here, story)
            if render_result["state"] != "succeeded":
                result = {"status": "withheld", "code": "renderer", "detail": render_result.get("error", render_result["state"]),
                          "repair": "Revise the opening narration or its visual cues to address the renderer message."}
            else:
                result = review(args_here, brief, approved, identity)
        except (RuntimeError, URLError, KeyError, ValueError, OSError, subprocess.SubprocessError) as error:
            result = {"status": "withheld", "code": "stage_error", "detail": str(error) or type(error).__name__}
        persist(out / "opening-outcome.json", result)
        study(args_here, root, out, story, result)
        if i == 0 and not first.exists():
            persist(first, {**identity, **result})
        if result["status"] == "accepted" or not result.get("repair"):
            break
        previous = result
    persist(terminal, {**identity, **result, "attempts": i+1})
    print(terminal.read_text(), end="")
