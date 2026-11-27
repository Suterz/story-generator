"""Chaptered educational production through the normal writer and video services."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from episode_graphics import RENDER


def chapter_schema(ids):
    return {
        "type": "object", "additionalProperties": False, "required": ["sections"],
        "properties": {"sections": {"type": "array", "minItems": len(ids), "maxItems": len(ids),
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["stage", "text", "caption", "cue"],
                      "properties": {"stage": {"enum": ids}, "text": {"type": "string", "minLength": 1},
                                     "caption": {"type": "string"}, "cue": {"type": "string"}}}}},
    }


def skill_for(brief, experiment):
    shared = ("Explain a mechanism to one curious adult, using only the supplied claims. "
              "Start on the question, connect each visual change to a spoken observation and end on why it matters. "
              "Use plain spoken words, not stage directions. Spell numbers out in narration. "
              "Use a concise caption that is faithful to speech, not a camera description.")
    techniques = {
        "entities": "Name stable objects and observers before drafting. Keep their identity across states.",
        "purpose": "At each state resolve the current question and leave a consequence that motivates the next. Pay off the opening.",
        "continuity": "Before drafting trace what changes versus what remains, including ownership. Narrate the change without losing the invariant.",
        "visual-first": "Start from what is inspectable in each visual state. Direct the eye to the exact element before explaining the inference.",
        "verification": "Keep the question's population, measured quantity and scope beside the actual supporting words. Distinguish plausible sources from support.",
    }
    routes = {"spatial": ("entities",), "worked-example": ("continuity",),
              "source-verification": ("verification",)}
    if experiment == "routed":
        chosen = ("purpose", "visual-first", *routes.get(brief["obligation"], ()))
    elif experiment == "baseline":
        chosen = ()
    else:
        chosen = (experiment,)
    return shared + "\n" + "\n".join(techniques[k] for k in chosen), chosen


def prompt_for(brief, experiment, revision=None, episode=False):
    skill, chosen = skill_for(brief, experiment)
    # Transfer answers are for review and are never needed to generate narration.
    source = {k: v for k, v in brief.items() if k != "transfer"}
    budget = brief.get("words", "55-73" if not episode else "90-125")
    prompt = (f"{skill}\nWrite about {budget} words across the supplied evidence states. "
              "Output one section per state in exactly the supplied order. A section can contain several natural sentences. "
              "Choose a short exact spoken cue for the change, preferably the first few spoken words of that section. "
              "The first cue may be empty. For every later section give a unique phrase from its own text. "
              "Only the supplied visual states are available; do not speak as if a different picture were shown. "
              "Do not include section labels in spoken text. Do not add a recap if the last insight already lands.\n"
              + json.dumps(source, ensure_ascii=False))
    if revision:
        prompt += "\nPrevious candidate was withheld for this concrete problem. Fix it without changing the brief:\n" + revision
    return prompt, chosen


def compile_chapter(brief, draft, prefix, *, short=True):
    from storygen import words

    ids = [s[0] for s in brief["stages"]]
    Draft202012Validator(chapter_schema(ids)).validate(draft)
    sections = draft["sections"]
    if [s["stage"] for s in sections] != ids:
        raise ValueError("required evidence states must be shown once in order")
    count = sum(len(words(s["text"])) for s in sections)
    if short and not 42 <= count <= 75:
        raise ValueError(f"preview narration has {count} words; use 55–73 words")
    script, beats = [], []
    for i, section in enumerate(sections):
        stage = section["stage"]
        ident = f"{prefix}-{stage}"
        spoken = section["text"].strip()
        caption = section["caption"].strip()
        if not spoken or not caption or len(caption) > 84:
            raise ValueError(f"{stage}: give narration and a faithful caption of at most 84 characters")
        cue = {"ms": 0}
        if i:
            candidate = words(section["cue"])
            spoken_words = words(spoken)
            matches = [j for j in range(len(spoken_words))
                       if spoken_words[j:j + len(candidate)] == candidate]
            if not candidate or len(matches) != 1 or matches[0] > 6:
                raise ValueError(f"{stage}: cue must bind once near the beginning of its own narration")
            cue = {"utterance_id": ident, "phrase": section["cue"]}
        overlays = RENDER[brief["obligation"]](stage)
        panel = {"op": "new_scene" if not i else "overlay_only", "scene_id": prefix,
                 "objective": brief["stages"][i][1], "instruction": "Compose the controlled evidence on paper.",
                 "overlays": overlays, "retry_budget": 0}
        if not i:
            panel["paper_scene"] = True
        script.append({"id": ident, "text": spoken, "caption": caption})
        beats.append({"id": ident, "cue": cue, "panel": panel,
                      **({"parent": beats[-1]["id"]} if i else {})})
    return script, beats


def write_chapter(args, brief, folder, endpoint, *, short=True, prefix="chapter"):
    from storygen import read, request, save

    folder.mkdir(parents=True, exist_ok=True)
    schema = chapter_schema([s[0] for s in brief["stages"]])
    reason = None
    for attempt in range(2):
        prompt, selected = prompt_for(brief, args.episode_skill, reason, episode=not short)
        payload = {"messages": [{"role": "user", "content": prompt}],
                   "temperature": .3, "top_p": .95, "seed": 437, "max_tokens": 1800,
                   "response_format": {"type": "json_schema", "json_schema": {"name": "chapter", "schema": schema}}}
        receipt = folder / f"writer-attempt-{attempt}.receipt.json"
        response_file = folder / f"writer-attempt-{attempt}.json"
        identity = {"request_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                    "skills": selected}
        identity["skills"] = list(identity["skills"])
        if receipt.exists() and read(receipt) != identity:
            raise ValueError("writer receipt inputs changed")
        if response_file.exists():
            response = read(response_file)
        else:
            if receipt.exists():
                raise RuntimeError(f"unknown writer outcome: {receipt}")
            save(receipt, identity)
            response = json.loads(request(endpoint + "/v1/chat/completions", payload, timeout=240))
            save(response_file, response)
        try:
            draft = json.loads(response["choices"][0]["message"]["content"])
            return compile_chapter(brief, draft, prefix, short=short)
        except (ValueError, KeyError, IndexError) as error:
            reason = str(error).splitlines()[0]
    raise ValueError(reason)


def run(args):
    from storygen import ROOT, SIGNATURES, read, render, save, validate, validate_native, writer

    brief = read(args.input)
    if brief.get("schema_version") != "episode/1":
        raise ValueError("expected episode/1")
    model = read(ROOT / "models.json")[args.model]
    config = {"brief": brief, "model": model, "skill": args.episode_skill, "voice": args.voice,
              "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "graphics": hashlib.sha256(Path(__file__).with_name("episode_graphics.py").read_bytes()).hexdigest()}
    metadata = args.out / "episode.json"
    if metadata.exists() and read(metadata) != config:
        raise ValueError("episode run inputs changed")
    save(metadata, config)
    file = args.out / "story.json"
    if not file.exists():
        try:
            with writer(args, args.models / model["file"], args.out / "llama.log") as endpoint:
                script, beats = write_chapter(args, brief, args.out, endpoint)
            story = {"title": brief["topic"],
                     "visual": {"story_context": brief["objective"], "visual_signature": SIGNATURES["paper"],
                                "graphic_theme": "paper"},
                     "voice_profile": args.voice, "script": script, "beats": beats, "max_ms": 44999}
            validate_native(validate(story))
        except ValueError as error:
            save(args.out / "result.json", {"status": "writer_refusal", "reason": str(error)})
            return
        save(file, story)
    if args.command == "run":
        print(json.dumps(render(args, read(file)), ensure_ascii=False))
