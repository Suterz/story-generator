"""Chaptered educational production through the normal writer and video services."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from episode_graphics import CITATION_PACKET, RENDER


def chapter_schema(ids, compact=False, *, sentences=False):
    if sentences:
        per_stage = 2 if len(ids) >= 3 else 3
        text = {"type": "array", "minItems": per_stage, "maxItems": per_stage,
                "items": {"type": "string", "minLength": 45, "maxLength": 153}}
    else:
        text = {"type": "string", "minLength": 1, **({"maxLength": 183} if compact else {})}
    return {
        "type": "object", "additionalProperties": False, "required": ["sections"],
        "properties": {"sections": {"type": "array", "minItems": len(ids), "maxItems": len(ids),
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["stage", "text", "caption", "cue"],
                      "properties": {"stage": {"enum": list(dict.fromkeys(ids))}, "text": text,
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
              "Choose a cue for each change: use START to cut on the first spoken words, "
              "or give two to five exact spoken words from the start of the section. "
              "Use START when a new chapter starts. Stage descriptions are never cue phrases. "
              "Only the supplied visual states are available; do not speak as if a different picture were shown. "
              "In this chapter say only the approved chapter claims; don't solve the next chapter's question in advance. "
              "Do not include section labels in spoken text. Do not add a recap if the last insight already lands.\n"
              + json.dumps(source, ensure_ascii=False))
    if revision:
        prompt += "\nPrevious candidate was withheld for this concrete problem. Fix it without changing the brief:\n" + revision
    return prompt, chosen


def compile_chapter(brief, draft, prefix, *, short=True):
    from storygen import words

    ids = [s[0] for s in brief["stages"]]
    errors = list(Draft202012Validator(chapter_schema(ids)).iter_errors(draft))
    if errors:
        raise ValueError(errors[0].message)
    sections = draft["sections"]
    if [s["stage"] for s in sections] != ids:
        raise ValueError("required evidence states must be shown once in order")
    count = sum(len(words(s["text"])) for s in sections)
    if short and not 42 <= count <= 96:
        raise ValueError(f"preview narration has {count} words; use 55–85 words")
    if not short and not 86 <= count <= 166:
        raise ValueError(f"chapter has {count} words; use around 20 words per sentence")
    script, beats = [], []
    for i, section in enumerate(sections):
        stage = section["stage"]
        ident = f"{prefix}-{i + 1}-{stage}"
        spoken = section["text"].strip()
        caption = section["caption"].strip()
        if not spoken or not spoken.rstrip("\"”’").endswith((".", "?", "!")):
            raise ValueError(f"{stage}: finish the full spoken sentence with punctuation")
        if short and (not caption or len(caption) > 84):
            raise ValueError(f"{stage}: give narration and a faithful caption of at most 84 characters")
        cue = {"ms": 0}
        if i or not short:
            if section["cue"].strip().upper() == "START" or (not i and not section["cue"].strip()):
                section = {**section, "cue": " ".join(spoken.split()[:3])}
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
        if short:
            script.append({"id": ident, "text": spoken, "caption": caption})
        else:
            import textwrap

            fragments = textwrap.wrap(spoken, width=82, break_long_words=False, break_on_hyphens=False)
            # Preserve authorship: captions use the actual narrated words. A
            # cue crossing a wrapping boundary stays in one utterance.
            if candidate and not any(_has_phrase(words(chunk), candidate) for chunk in fragments):
                fragments = [" ".join(fragments[:2]), *fragments[2:]]
            for j, fragment in enumerate(fragments):
                utterance_id = f"{ident}-{j + 1}"
                script.append({"id": utterance_id, "text": fragment, "caption": fragment})
                if _has_phrase(words(fragment), candidate):
                    cue["utterance_id"] = utterance_id
            if cue["utterance_id"] == ident:
                raise ValueError(f"{stage}: cue crosses an unsupported caption boundary")
        beats.append({"id": ident, "cue": cue, "panel": panel,
                      **({"parent": beats[-1]["id"]} if i else {})})
    return script, beats


def _has_phrase(tokens, phrase):
    return bool(phrase) and any(tokens[j:j + len(phrase)] == phrase for j in range(len(tokens)))


def write_chapter(args, brief, folder, endpoint, *, short=True, prefix="chapter"):
    from storygen import read, request, save

    folder.mkdir(parents=True, exist_ok=True)
    ids = [s[0] for s in brief["stages"]]
    schema = chapter_schema(ids, compact=short, sentences=not short)
    reason = None
    for attempt in range(2):
        prompt, selected = prompt_for(brief, args.episode_skill, reason, episode=not short)
        if short:
            prompt += ("\nHard limit: each of the three text fields is one short sentence, roughly twenty words, "
                       "and no more than 183 characters including final punctuation. "
                       "The final text must be short enough to speak in under forty-five seconds.")
        else:
            prompt += ("\nEach text value is an array of complete spoken sentences, around twenty words each. "
                       "For three visual states, use exactly two sentences at each state. For two use three each. "
                       "Aim for 105 to 139 words in this whole chapter. Do not put START or directions in the actual speech.")
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
            errors = list(Draft202012Validator(schema).iter_errors(draft))
            if errors:
                raise ValueError(errors[0].message)
            if not short:
                for section in draft["sections"]:
                    if any(not s.rstrip(" \"”’").endswith((".", "?", "!")) for s in section["text"]):
                        raise ValueError("Every sentence in the array must be complete and end with punctuation")
                    section["text"] = " ".join(section["text"])
            return compile_chapter(brief, draft, prefix, short=short)
        except (ValueError, KeyError, IndexError) as error:
            reason = str(error).splitlines()[0]
    raise ValueError(reason)


def write_episode(args, brief, out, endpoint):
    script, beats, starts = [], [], []
    for i, chapter in enumerate(brief["chapters"], 1):
        label = f"c{i:02d}"
        chapter_brief = {k: v for k, v in brief.items() if k not in
                         ("chapters", "transfer", "claims", "stages", "question", "id", "min_ms")}
        chapter_brief.update(chapter)
        chapter_brief["episode_continuity"] = {
            "previous": brief["chapters"][i - 2]["question"] if i > 1 else None,
            "next": brief["chapters"][i]["question"] if i < len(brief["chapters"]) else None,
            "position": f"{i} of {len(brief['chapters'])}",
        }
        part, visuals = write_chapter(args, chapter_brief, out / "chapters" / label, endpoint,
                                      short=False, prefix=label)
        starts.append(part[0]["id"])
        script.extend(part)
        beats.extend(visuals)
    beats[0]["cue"] = {"ms": 0}
    count = sum(len(u["text"].split()) for u in script)
    minimum = 520 if brief["min_ms"] == 180000 else 350
    if not minimum <= count <= 820:
        raise ValueError(f"episode authored {count} words, outside {minimum}–820")
    return script, beats, starts


def run(args):
    from storygen import ROOT, SIGNATURES, read, render, save, validate, validate_native, writer

    brief = read(args.input)
    if brief.get("schema_version") != "episode/1":
        raise ValueError("expected episode/1")
    model = read(ROOT / "models.json")[args.model]
    config = {"brief": brief, "model": model, "skill": args.episode_skill, "voice": args.voice,
              "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "graphics": hashlib.sha256(Path(__file__).with_name("episode_graphics.py").read_bytes()).hexdigest()}
    if brief["obligation"] == "source-verification":
        from source_pack import evidence_for

        config["source_packet"] = hashlib.sha256(CITATION_PACKET.read_bytes()).hexdigest()
        save(args.out / "source-evidence.json", evidence_for(read(CITATION_PACKET)))
    metadata = args.out / "episode.json"
    if metadata.exists() and read(metadata) != config:
        raise ValueError("episode run inputs changed")
    save(metadata, config)
    file = args.out / "story.json"
    if not file.exists():
        full = "chapters" in brief
        try:
            with writer(args, args.models / model["file"], args.out / "llama.log") as endpoint:
                if full:
                    script, beats, starts = write_episode(args, brief, args.out, endpoint)
                else:
                    script, beats = write_chapter(args, brief, args.out, endpoint)
            story = {"title": brief["topic"],
                     "visual": {"story_context": brief["objective"], "visual_signature": SIGNATURES["paper"],
                                "graphic_theme": "paper"},
                     "voice_profile": args.voice, "script": script, "beats": beats, "max_ms": 44999}
            if full:
                story.update(chapter_starts=starts, min_ms=brief["min_ms"], max_ms=300000)
            validate_native(story if full else validate(story, max_words=96))
        except ValueError as error:
            save(args.out / "result.json", {"status": "writer_refusal", "reason": str(error)})
            return
        save(file, story)
    if args.command == "run":
        print(json.dumps(render(args, read(file)), ensure_ascii=False))
