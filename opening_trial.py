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


def compile_preview(brief, plan, approved, voice):
    from storygen import SIGNATURES, words

    script, beats = [], []
    for i, section in enumerate(plan["states"], 1):
        key = f"opening-{i}"
        if not set(section["claim_ids"]) <= approved:
            raise ValueError(f"{key}: unsupported claim ID")
        narration = section["narration"]
        cue = " ".join(words(narration)[:4])
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
                "endpoint": args.video_url, "seed": 437}
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
                    if args.opening_preview == "baseline-v1":
                        outline = ask(endpoint, BASELINE, packet, DAILY_OUTLINE, 1250, out / "outline-response.json")
                        packet["outline"] = outline
                        instruction = "Follow the proposed opening. " + EXECUTE
                    else:
                        selected = (QUESTION_BEFORE_ANSWER if args.opening_preview == "question-before-answer-v3"
                                    else VISIBLE_QUESTION)
                        instruction = selected + " " + EXECUTE
                    if previous:
                        instruction += " Repair only the specific observed defect and preserve the supported facts."
                    plan = ask(endpoint, instruction, packet, OPEN, 2000, out / "plan-response.json")
                persist(out / "plan.json", plan)
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
