"""Local brief-to-story CLI, with durable one-submit rendering."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import os
import re
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, ValidationError

from arithmetic import checked_comparisons
from communication import NeedsInput, UnsupportedBrief, check_supplied_authority, extract, intent_hash, normalize
from graphics import COUNTER_ROW, expand_counter_rows
from spoken_money import normalize_story_money


ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skills/lesson-writer/v4/SKILL.md"
COMMUNICATION_SKILL = ROOT / "skills/communication-writer/v2/SKILL.md"
HOME = Path.home()
SIGNATURES = {
    "market": "Original editorial cartoon, strong plum outlines, warm ivory paper, bright ochre fruit, teal leaves, rounded simple silhouettes.",
    "paper": "Standalone explanatory cartoon with warm cut-paper silhouettes, dark outlines, and minimal decoration.",
}
MEASUREMENT = {
    "type": "object", "properties": {"name": {"type": "string"}, "expression": {"type": "string"}},
    "required": ["name", "expression"], "additionalProperties": False,
}
EDITORIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {"type": "string"},
        "comparisons": {"type": "array", "maxItems": 8, "items": {
            "type": "object", "properties": {"a": MEASUREMENT, "b": MEASUREMENT, "unit": {"type": "string"}},
            "required": ["a", "b", "unit"], "additionalProperties": False,
        }},
    },
    "required": ["notes", "comparisons"], "additionalProperties": False,
}
OUTPUT_GRAMMAR = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "visual": {"type": "object", "additionalProperties": True},
        "script": {"type": "array", "items": {
            "type": "object", "properties": {
                "id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]{0,79}$"}, "text": {"type": "string"},
                "caption": {"type": "string"}, "pause_after_ms": {"type": "integer"},
                "critical_spoken": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            }, "required": ["id", "text"], "additionalProperties": False,
        }},
        "beats": {"type": "array", "items": {
            "type": "object", "properties": {
                "id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]{0,79}$"},
                "parent": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]{0,79}$"},
                "cue": {"type": "object", "additionalProperties": True},
                "panel": {"type": "object", "additionalProperties": True},
            }, "required": ["id", "cue", "panel"], "additionalProperties": False,
        }},
        "instructional": {"type": "object", "additionalProperties": True},
    },
    "required": ["title", "visual", "script", "beats", "instructional"],
    "additionalProperties": False,
}


def generation_schema(*, communication=False, prediction=True):
    # Use the versioned renderer properties, with a small authored subset.
    video = read(ROOT / "schemas/Video.json")
    session = read(ROOT / "schemas/Session.json")
    panel = read(ROOT / "schemas/Panel.json")
    panel["properties"].pop("key")
    panel["properties"].pop("parent_panel_id")
    panel["properties"]["counter_rows"] = {"type": "array", "maxItems": 3, "items": COUNTER_ROW}
    panel["required"] = ["op", "objective", "instruction", "overlays"]
    session["required"] = ["story_context", "visual_signature", "graphic_theme"]
    if communication:
        # Communication plans keep their evaluated comparisons separately.
        # The renderer's session checks only support the specific legacy
        # equal-groups operand contract, not general editorial arithmetic.
        for name in ("style_ref_ids", "legacy_input", "legacy_premise", "legacy_context", "checks"):
            session["properties"].pop(name, None)
    schema = json.loads(json.dumps(OUTPUT_GRAMMAR))
    if communication:
        schema["required"].remove("instructional")
    schema["$defs"] = {**video["$defs"], **session.pop("$defs", {}), **panel.pop("$defs", {})}
    instruction = schema["$defs"]["Instructional"]
    instruction["properties"].pop("required_facts")
    instruction["required"].remove("required_facts")
    graphic_props = schema["$defs"]["Overlay"]["properties"]

    def graphic(kind, required, optional=(), shape=None):
        props = {k: graphic_props[k] for k in (*required, *optional, "fact")}
        for key in required:
            if "anyOf" in props[key]:
                props[key] = {"anyOf": [option for option in props[key]["anyOf"]
                                       if option.get("type") != "null"]}
        props["type"] = {"const": kind}
        if shape:
            props["shape"] = {"const": shape}
        return {"type": "object", "properties": props,
                "required": ["type", *required, *(["shape"] if shape else [])],
                "additionalProperties": False}

    text = ("at", "text")
    schema["$defs"]["Overlay"] = {"anyOf": [
        graphic("text", text, ["role"]),
        graphic("label", text, ["role"]),
        graphic("arrow", ["from", "to"], ["part_target", "part_relation", "target_region", "target_rgb"]),
        graphic("segment", ["from", "to"], ["divisions", "ink"]),
        graphic("shape", ["at", "extent"], ["ink"], "rect"),
        graphic("shape", ["at", "extent"], ["ink"], "disc"),
        graphic("shape", ["vertices"], ["ink"], "polygon"),
    ]}
    schema["properties"]["visual"] = session
    schema["properties"]["instructional"] = {"$ref": "#/$defs/Instructional"}
    if communication and not prediction:
        del schema["properties"]["instructional"]
    beat = schema["properties"]["beats"]["items"]["properties"]
    starts = {"type": "object", "properties": {"at_utterance_start": {"type": "string"}},
              "required": ["at_utterance_start"], "additionalProperties": False}
    beat["cue"] = {"anyOf": [{"$ref": "#/$defs/Milliseconds"}, starts, {"$ref": "#/$defs/Phrase"}]}
    beat["panel"] = panel
    def grammar_subset(node):
        # b6500 cannot translate every regex supported by JSON Schema.
        # Full schema validation still runs after generation.
        if isinstance(node, dict):
            return {key: grammar_subset(value) for key, value in node.items()
                    if key != "pattern" or (value.startswith("^") and value.endswith("$") and "\\w" not in value)}
        if isinstance(node, list):
            return [grammar_subset(value) for value in node]
        return node

    return grammar_subset(schema)


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def request(url, data=None, headers=None, timeout=30):
    body = None if data is None else json.dumps(data).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def brief_rule(brief):
    names = {"topic", "takeaway", "audience", "signature", "required_facts"}
    if not isinstance(brief, dict) or not names <= set(brief) <= names | {"artwork"}:
        raise ValueError("brief requires topic, takeaway, audience, signature and required_facts")
    if brief.get("artwork", "auto") not in ("auto", "paper"):
        raise ValueError("artwork must be auto or paper")
    if not all(isinstance(brief[k], str) and brief[k].strip() for k in names - {"required_facts"}):
        raise ValueError("brief text fields must not be blank")
    facts = brief["required_facts"]
    if not isinstance(facts, list) or not facts or not all(isinstance(v, str) and v.strip() for v in facts):
        raise ValueError("required_facts must be a nonempty list of text")
    if brief["signature"] not in SIGNATURES:
        raise ValueError(f"unknown signature: {brief['signature']}")


def choose_artwork(story, brief):
    """An explicit paper brief uses only the author's controlled graphics."""
    if brief.get("artwork") != "paper":
        return story
    for beat in story["beats"]:
        panel = beat["panel"]
        if (panel["op"] not in ("new_scene", "overlay_only") or
                any(panel.get(field) for field in ("layout", "fallback_layout", "anchors"))):
            raise ValueError("paper artwork needs new_scene or overlay_only with authored graphics, without generated anchors or layouts")
        if panel["op"] == "new_scene":
            panel["paper_scene"] = True
        if not (panel.get("overlays") or panel.get("counter_rows")):
            raise ValueError("paper artwork needs visible authored graphics")
    return story


def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.replace("’", "'").lower())


def compile_story(story):
    """Resolve authored ancestry and utterance starts into API identifiers."""
    texts = {u["id"]: u["text"] for u in story["script"]}
    scenes = {}
    previous = None
    for beat in story["beats"]:
        panel = beat["panel"]
        if not isinstance(panel, dict):
            raise ValueError("each beat needs a panel object with op, instruction, objective and overlays")
        expand_counter_rows(panel)
        if panel.get("op") != "new_scene" and not beat.get("parent") and previous is not None:
            # Edit and overlay explicitly continue the existing scene. The
            # immediate preceding beat is the default source of that artwork.
            beat["parent"] = previous
        scene = scenes[beat["parent"]] if beat.get("parent") else beat["id"]
        if panel.get("scene_id", scene) != scene and beat.get("parent"):
            raise ValueError("an existing scene must preserve its parent's scene_id")
        scenes[beat["id"]] = panel.setdefault("scene_id", scene)
        previous = beat["id"]
        cue = beat["cue"]
        if "at_utterance_start" not in cue:
            continue
        if set(cue) != {"at_utterance_start"}:
            raise ValueError("utterance-start cue cannot have other fields")
        key = cue["at_utterance_start"]
        tokens = words(texts[key])
        if not tokens:
            raise ValueError("utterance-start cue has no spoken words")
        beat["cue"] = {"utterance_id": key, "phrase": " ".join(tokens[:min(4, len(tokens))]), "occurrence": 1}
    rule = story.get("instructional")
    if rule and "required_facts" not in rule:
        visible = prediction_panel(story, rule)
        rule["required_facts"] = [item["fact"] for item in visible["panel"].get("overlays", [])
                                  if item.get("fact")]
        if not rule["required_facts"]:
            raise ValueError("mark the question's actual visible clues using overlay fact IDs")
    return story


def prediction_panel(story, rule):
    order = [u["id"] for u in story["script"]]
    question = order.index(rule["question_utterance"])
    return next(b for b in reversed(story["beats"])
                if "ms" in b["cue"] or order.index(b["cue"]["utterance_id"]) <= question)


def validate(story):
    for name, data in (("Video", story), ("Session", story["visual"])):
        Draft202012Validator(read(ROOT / "schemas" / f"{name}.json")).validate(data)
    panel = Draft202012Validator(read(ROOT / "schemas/Panel.json"))
    script = {u["id"]: u for u in story["script"]}
    order = list(script)
    if len(script) != len(story["script"]):
        raise ValueError("duplicate script ID")
    if sum(len(words(u["text"])) for u in script.values()) > 75:
        raise ValueError("shorten narration to no more than 75 spoken tokens")
    if story["beats"][0]["cue"] != {"ms": 0}:
        raise ValueError("opening beat must start at ms=0")
    seen = {}
    previous = (-1, -1)
    for pos, b in enumerate(story["beats"]):
        key, parent, spec = b["id"], b.get("parent"), b["panel"]
        if key in seen or parent and parent not in seen:
            raise ValueError(f"{key}: duplicate beat or unavailable parent")
        if (spec["op"] == "new_scene") == bool(parent):
            raise ValueError(f"{key}: only a new scene has no parent")
        panel.validate({**spec, "key": key, "parent_panel_id": "a" * 32 if parent else None})
        for graphic in spec.get("overlays", []):
            if graphic["type"] in ("text", "label") and not (graphic.get("text") or "").strip():
                raise ValueError(f"{key}: text overlays must contain visible text")
            if graphic["type"] != "arrow" and any(graphic.get(x) is not None for x in ("target_region", "target_rgb", "part_target")):
                raise ValueError(f"{key}: part targeting fields apply only to arrows")
        cue = b["cue"]
        if pos:
            if "ms" in cue:
                raise ValueError(f"{key}: use a spoken phrase or authored utterance start after the opening")
            parts = words(cue["phrase"])
            utterance = words(script[cue["utterance_id"]]["text"])
            indexes = [i for i in range(len(utterance)) if utterance[i:i + len(parts)] == parts]
            n = cue.get("occurrence")
            if not parts or (n is None and len(indexes) != 1) or (n is not None and n > len(indexes)):
                raise ValueError(f"{key}: cue does not uniquely bind to the spoken words")
            place = (order.index(cue["utterance_id"]), indexes[(n or 1) - 1])
            if place <= previous:
                raise ValueError(f"{key}: cue must follow the preceding panel")
            previous = place
        seen[key] = b
    rule = story.get("instructional")
    if rule:
        question = script[rule["question_utterance"]]
        if question.get("pause_after_ms", 0) < rule.get("minimum_ms", 1200):
            raise ValueError("prediction pause shorter than authored minimum")
        answer = seen[rule["answer_beat"]]
        if order.index(answer["cue"]["utterance_id"]) <= order.index(question["id"]):
            raise ValueError("answer beat is not after the question")
        active = prediction_panel(story, rule)
        marks = {item.get("fact") for item in active["panel"].get("overlays", [])}
        if not set(rule["required_facts"]) <= marks:
            raise ValueError("question panel does not draw each instructional required_facts overlay")
        for phrase in rule.get("spoken_answer_phrases", []):
            sought = words(phrase)
            if len(sought) < 2:
                raise ValueError("a spoken answer phrase needs at least two actual words")
            found = []
            for index, utterance in enumerate(script.values()):
                line = words(utterance["text"])
                found.extend((index, offset) for offset in range(len(line))
                             if line[offset:offset + len(sought)] == sought)
            if not found:
                raise ValueError(f"spoken answer phrase {phrase!r} must occur verbatim in the narration")
            onset = answer["cue"]
            if any(index < order.index(onset["utterance_id"]) for index, _ in found):
                raise ValueError(f"spoken answer phrase {phrase!r} occurs in an earlier utterance")
    return story


def validate_native(story):
    python = os.environ.get("STORYGEN_VALIDATOR_PYTHON")
    sources = os.environ.get("STORYGEN_RENDERER_SOURCES")
    if bool(python) != bool(sources):
        raise ValueError("native preflight requires both the validator Python and renderer source paths")
    if not python:
        return story
    result = subprocess.run([python, "-B", str(ROOT / "native_preflight.py")],
                              input=json.dumps(story), text=True, capture_output=True,
                              env={**os.environ, "PYTHONPATH": sources}, timeout=30)
    if result.returncode == 2:
        raise ValueError("native renderer preflight: " + result.stdout.strip()[:900])
    if result.returncode:
        raise RuntimeError("native renderer validator failed: " + result.stderr[-800:])
    return story


def check_editorial_conclusion(story, comparisons):
    if not {"<", ">"} <= {entry["relation"] for entry in comparisons}:
        return
    conclusion = re.split(r"[.!?]\s+", story["script"][-1]["text"].rstrip(".! "))[-1]
    criterion = r"\b(?:per [a-z]+|at checkout|by [a-z]+|in terms of [a-z]+|on [a-z]+ alone)\b"
    if re.search(r"\bbetter\s+than\b", conclusion, re.I) and not re.search(criterion, conclusion, re.I):
        raise ValueError("the last sentence names an overall winner across opposing criteria; name the criterion")


def check_communication_anchors(story):
    """Catch invented overlay anchors when no controlled layout can provide them."""
    available = {}
    for beat in story["beats"]:
        panel = beat["panel"]
        parent = beat.get("parent")
        inherited = available.get(parent, set()) if panel["op"] in {"overlay_only", "focus"} else set()
        if panel.get("layout") or panel.get("fallback_layout") or inherited is None:
            # Controlled geometry produces its own instance anchors; the
            # native frame service is the authority for those assets.
            available[beat["id"]] = None
            continue
        anchors = inherited | panel.get("anchors", {}).keys()
        available[beat["id"]] = anchors
        for overlay in panel.get("overlays", []):
            for key in ("at", "from", "to"):
                target = overlay.get(key)
                if isinstance(target, str) and target not in anchors | {"safe.top", "safe.bottom"}:
                    raise ValueError(f"{beat['id']}: overlay target {target!r} is not grounded; declare the intended surface on the clean scene")


@contextmanager
def writer(args, model, log):
    with args.lease.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        cmd = [str(args.runtime), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
               "-c", "8192", "-ngl", "99", "-np", "1", "--jinja"]
        with log.open("w") as stream:
            proc = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT)
            try:
                end = time.monotonic() + 120
                while time.monotonic() < end:
                    if proc.poll() is not None:
                        raise RuntimeError(f"writer startup failed: {log}")
                    try:
                        request(base + "/health", timeout=2)
                        break
                    except (URLError, TimeoutError):
                        time.sleep(.3)
                else:
                    raise TimeoutError("writer readiness timeout")
                yield base
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def load_brief(args, model, config):
    if not args.raw_text:
        incoming = read(args.input)
        if "schema_version" not in incoming:
            brief_rule(incoming)
            return incoming, False
        raw = None
    else:
        raw = args.input.read_text() if str(args.input) != "-" else sys.stdin.read()
        incoming = raw
    out = args.out
    record = out / "normalization.json"
    identity = {"input": incoming, "mode": "text" if args.raw_text else "structured"}
    if args.raw_text:
        identity["extractor"] = config
    if record.exists():
        prior = read(record)
        if prior["source"] != identity:
            raise ValueError("cannot resume normalization with different input")
        return prior["brief"], True
    if args.raw_text:
        receipt = out / "normalization-receipt.json"
        response_path = out / "normalization-model.json"
        if receipt.exists() and read(receipt) != identity:
            raise ValueError("cannot resume text extraction with different input or model")
        if not response_path.exists():
            if receipt.exists():
                raise RuntimeError("normalization was interrupted; no duplicate model request")
            with model.open("rb") as asset:
                if hashlib.file_digest(asset, "sha256").hexdigest() != config["sha256"]:
                    raise ValueError("normalizer checkpoint hash mismatch")
            with writer(args, model, out / "normalizer.log") as endpoint:
                def ask(prompt):
                    save(receipt, identity)
                    payload = {"messages": [{"role": "user", "content": prompt}], "seed": 437,
                               "temperature": 0, "max_tokens": 2200,
                               "response_format": {"type": "json_object"}}
                    response = json.loads(request(endpoint + "/v1/chat/completions", payload, timeout=150))
                    save(response_path, response)
                    return json.loads(response["choices"][0]["message"]["content"])
                brief, origins = extract(raw, ask, SIGNATURES)
        else:
            brief, origins = extract(raw, lambda _: json.loads(
                read(response_path)["choices"][0]["message"]["content"]), SIGNATURES)
    else:
        brief, origins = normalize(incoming, SIGNATURES)
    save(out / "normalized-brief.json", brief)
    save(out / "provenance.json", origins)
    save(record, {"source": identity, "brief": brief, "intent_sha256": intent_hash(brief)})
    return brief, True


def write(args):
    out = args.out
    config = read(ROOT / "models.json")[args.model]
    model = args.models / config["file"]
    brief, generic = load_brief(args, model, config)
    if generic:
        check_supplied_authority(brief)
    skill_path = COMMUNICATION_SKILL if generic else SKILL
    skill = skill_path.read_text()
    example = (SKILL.parent / "annotated-example.json").read_text()
    meta = {"brief": brief, "model": config, "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "example_sha256": hashlib.sha256(example.encode()).hexdigest(),
            "seed": 437, "temperature": .6, "top_p": .95, "max_tokens": 3300, "voice": args.voice}
    if (out / "writer.json").exists() and read(out / "writer.json") != meta:
        raise ValueError("cannot resume with a changed brief or writer configuration")
    if (out / "story.json").exists():
        return validate_native(validate(read(out / "story.json")))
    if (out / "writer-refusal.json").exists():
        if generic:
            raise CommunicationReview(read(out / "writer-refusal.json")["diagnostics"][-1])
        raise ValueError("writer previously withheld this brief; original diagnostics saved")
    with model.open("rb") as asset:
        actual = hashlib.file_digest(asset, "sha256").hexdigest()
    if actual != config["sha256"]:
        raise ValueError("writer checkpoint hash mismatch")
    save(out / "writer.json", meta)
    errors = []
    with writer(args, model, out / "llama.log") as endpoint:
        plan_schema = EDITORIAL_SCHEMA
        if generic:
            plan_schema = {**EDITORIAL_SCHEMA,
                           "properties": {**EDITORIAL_SCHEMA["properties"], "prediction": {"type": "boolean"}},
                           "required": [*EDITORIAL_SCHEMA["required"], "prediction"]}
        plan_file = out / "editorial-plan.json"
        if plan_file.exists():
            plan = read(plan_file)
        else:
            plan_receipt = out / "editorial-plan.receipt.json"
            if plan_receipt.exists():
                raise RuntimeError("editorial planning was interrupted; no duplicate generation")
            if generic:
                editorial = (
                    "Return a JSON communication plan: in notes name the intended viewer effect, a natural opening, "
                    "the decisive visual evidence and what stays visible, and a distinct worthwhile ending. "
                    "Use only approved facts, preserve exact wording, and don't force a prediction. Set prediction "
                    "true only if showing clues, then waiting silently for a learner to guess a result is the best "
                    "way to communicate this objective. For wayfinding, a rhetorical question is not a prediction. "
                    "Comparisons is empty unless the topic itself requires a quantitative comparison. "
                    "Expressions contain numbers and + - * / only, never timestamps, units or duration budgets. Brief:\n"
                    + json.dumps({k: brief[k] for k in ("topic", "objective", "takeaway", "audience", "tone", "source_notes")},
                                 ensure_ascii=False)
                )
            else:
                editorial = (
                "Return a JSON editor's checklist for a beginner lesson. In notes state the given values, "
                "what the learner must infer, what must be visible before the question, "
                "and what physically changes at reveal. For each quantitative comparison, add two named "
                "quantities a and b as numeric expressions, with exactly the same unit for both. "
                "Use only the quantities from the brief, numbers and + - * /. The comparator computes "
                "which is smaller; do not put a guessed winner in notes. Use separate comparisons for "
                "total price and price per item, or elapsed time when waiting is part of the journey. "
                "If there is no quantitative comparison, provide an empty comparisons list.\n" +
                json.dumps(brief, ensure_ascii=False)
                )
            data = {"messages": [{"role": "user", "content": editorial}], "seed": meta["seed"],
                    "temperature": .3, "top_p": .95, "max_tokens": 650,
                    "response_format": {"type": "json_schema", "json_schema": {
                        "name": "lesson_editor", "schema": plan_schema}}}
            save(plan_receipt, {"request_sha256": hashlib.sha256(editorial.encode()).hexdigest()})
            plan = json.loads(request(endpoint + "/v1/chat/completions", data, timeout=120))
            save(plan_file, plan)
        checklist = json.loads(plan["choices"][0]["message"]["content"])
        Draft202012Validator(plan_schema).validate(checklist)
        prediction = checklist.get("prediction", True)
        if generic:
            comparisons = []
            for item in checklist["comparisons"]:
                try:
                    comparisons.extend(checked_comparisons([item]))
                except (ValueError, SyntaxError, ArithmeticError):
                    # An optional comparison containing prose provides no
                    # verified arithmetic evidence; never pass it on as such.
                    continue
        else:
            comparisons = checked_comparisons(checklist["comparisons"])
        save(out / "checked-comparisons.json", comparisons)
        checks = checklist["notes"] + "\nExact computations and ordering:\n" + json.dumps(comparisons, ensure_ascii=False)
        for attempt in range(2):
            artifact = out / f"writer-attempt-{attempt}.json"
            if artifact.exists():
                result = read(artifact)
            else:
                receipt = artifact.with_suffix(".receipt.json")
                if receipt.exists():
                    raise RuntimeError(f"writer attempt {attempt} was interrupted; no duplicate generation")
                if generic:
                    prompt = skill + "\nReturn JSON with title, visual, script and beats.\n"
                    if not prediction:
                        prompt += "The editorial plan chose no prediction. Omit instructional. "
                    prompt += ('Timing example: first beat cue {"ms":0}; any later beat cue '
                               '{"at_utterance_start":"id-of-spoken-utterance"}. '
                               "Do not invent millisecond estimates for later beats.\n")
                else:
                    prompt = skill + "\nRead this unrelated format example. Do not copy its values or topic:\n" + example
                    prompt += "\nReturn one JSON object with title, visual, script, beats, and instructional.\n"
                prompt += "Brief:\n" + json.dumps(brief, ensure_ascii=False)
                prompt += "\nCheck the plan against the brief, then write the complete teachable answer and actual overlays:\n" + (checks or "")
                prompt += ("\nGive an overlay fact ID only to a clue actually drawn before the question; "
                           "the compiler records those IDs. Include literal visible text in every text overlay. "
                           "Put exact answers in the reveal, attached to the right objects. "
                           "If comparisons use different criteria, name the criterion in each conclusion. "
                           "Never end a two-criterion tradeoff with an unspecified overall winner. "
                           "Spell out numbers and currency in narration; use numerals in graphics.")
                signature = brief["visual_signature" if generic else "signature"]
                prompt += "\nUse this exact visual signature: " + SIGNATURES[signature]
                if brief.get("artwork") == "paper":
                    prompt += ("\nThis brief explicitly selects paper artwork. Draw all evidence with shapes, "
                               "segments, labels or counter_rows. Use new_scene or overlay_only; no generated "
                               "anchors or cutout layouts.")
                if errors:
                    prompt += "\nCorrect this validation failure without changing any required fact: " + errors[-1]
                t = time.monotonic()
                data = {"messages": [{"role": "user", "content": prompt}],
                        "seed": meta["seed"], "temperature": meta["temperature"], "top_p": meta["top_p"],
                        "max_tokens": meta["max_tokens"],
                        "response_format": {"type": "json_schema", "json_schema": {
                            "name": "communication_story" if generic else "lesson_story",
                            "schema": generation_schema(communication=generic, prediction=prediction)}}}
                save(receipt, {"attempt": attempt, "request_sha256": hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()).hexdigest()})
                result = json.loads(request(endpoint + "/v1/chat/completions", data, timeout=240))
                save(artifact, {"seconds": time.monotonic() - t, "response": result})
                result = read(artifact)
            try:
                story = json.loads(result["response"]["choices"][0]["message"]["content"])
                story["voice_profile"] = args.voice
                story["visual"]["visual_signature"] = SIGNATURES[brief["visual_signature" if generic else "signature"]]
                if generic:
                    if not prediction and "instructional" in story:
                        raise ValueError("the editorial plan does not have a prediction interval")
                    if any(k in story["visual"] for k in ("style_ref_ids", "legacy_input", "legacy_premise", "legacy_context")):
                        raise ValueError("use the supplied signature; this brief did not supply uploaded style references or a legacy story")
                    if story["visual"].get("checks"):
                        raise ValueError("keep editorial calculations out of the frame session checks")
                    story["max_ms"] = brief["max_duration_ms"]
                choose_artwork(story, brief)
                if generic and any(n["kind"] == "verbatim" for n in brief["source_notes"]):
                    # Exact supplied wording takes precedence over spoken
                    # currency rewriting; an unalignable quote is withheld.
                    validate_native(validate(compile_story(story)))
                else:
                    validate_native(validate(compile_story(normalize_story_money(story))))
                if generic:
                    check_communication_anchors(story)
                    text = " ".join(u["text"] for u in story["script"])
                    if any(n["kind"] == "verbatim" and n["text"] not in text for n in brief["source_notes"]):
                        raise ValueError("approved verbatim wording is missing from the spoken script")
                check_editorial_conclusion(story, comparisons)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(str(exc))
            except ValidationError as exc:
                errors.append(f"{list(exc.path)}: {exc.message[:500]}")
            else:
                save(out / "story.json", story)
                return story
    save(out / "writer-refusal.json", {"diagnostics": errors})
    if generic:
        raise CommunicationReview(errors[-1])
    raise ValueError("writer did not produce a supported story: " + errors[-1])


class CommunicationReview(ValueError):
    pass


def render(args, story):
    out = args.out
    digest = hashlib.sha256(json.dumps(story, sort_keys=True).encode()).hexdigest()
    key = "storygen-" + hashlib.sha256(f"{out.resolve()}:{digest}".encode()).hexdigest()
    receipt = out / "submission.json"
    base = args.video_url.rstrip("/")
    info = {"key": key, "digest": digest, "endpoint": base}
    if receipt.exists():
        if read(receipt) != info:
            raise ValueError("cannot resume with a different story or endpoint")
        if (out / "outcome.json").exists():
            return read(out / "outcome.json")
        status = json.loads(request(f"{base}/v2/submissions/{key}"))
    else:
        save(receipt, info)
        status = json.loads(request(base + "/v2/renders", story, {"Idempotency-Key": key}))
    deadline = time.monotonic() + 1800
    while status["state"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(2)
        status = json.loads(request(base + status["status_url"]))
    if status["state"] in {"queued", "running"}:
        raise TimeoutError("job still active; resume with the same output directory")
    if status["state"] == "succeeded":
        video = request(base + status["video_url"])
        (out / "video.partial.mp4").write_bytes(video)
        (out / "video.partial.mp4").replace(out / "video.mp4")
        save(out / "manifest.json", json.loads(request(base + status["status_url"] + "/manifest")))
        status["download_sha256"] = hashlib.sha256(video).hexdigest()
    save(out / "outcome.json", status)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("normalize", "write", "render", "run"))
    p.add_argument("input", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--video-url", default="http://127.0.0.1:8893")
    p.add_argument("--model", choices=tuple(read(ROOT / "models.json")), default="qwen")
    p.add_argument("--models", type=Path, default=HOME / "ai/storyboard-rehearsal/writer/models")
    p.add_argument("--runtime", type=Path, default=HOME / "ai/storyboard-rehearsal/writer/runtime/build/bin/llama-server")
    p.add_argument("--lease", type=Path, default=HOME / "ai/storyboard-build/v2/gpu.lock")
    p.add_argument("--voice", choices=("heart", "ryan"), default="ryan")
    p.add_argument("--raw-text", action="store_true", help="read a rough brief from a text file or stdin (-)")
    p.add_argument("--validator-python", type=Path, help="Python with the renderer dependencies")
    p.add_argument("--frames-repo", type=Path, help="frames-renderer checkout matching the server")
    p.add_argument("--video-repo", type=Path, help="video-renderer checkout matching the server")
    args = p.parse_args()
    native = (args.validator_python, args.frames_repo, args.video_repo)
    if any(native):
        if not all(native):
            p.error("--validator-python, --frames-repo and --video-repo must be supplied together")
        # Resolve the directory relative to the caller, not a venv Python
        # symlink: the interpreter needs the neighboring pyvenv.cfg.
        os.environ["STORYGEN_VALIDATOR_PYTHON"] = str(args.validator_python.absolute())
        os.environ["STORYGEN_RENDERER_SOURCES"] = os.pathsep.join(
            str(root.resolve() / "src") for root in (args.frames_repo, args.video_repo))
    if not os.environ.get("STORYGEN_VALIDATOR_PYTHON") and not os.environ.get("STORYGEN_RENDERER_SOURCES"):
        print("Using schema-only validation; native renderer preflight is not configured.", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.command == "normalize":
                config = read(ROOT / "models.json")[args.model]
                brief, generic = load_brief(args, args.models / config["file"], config)
                if not generic:
                    p.error("normalize expects a versioned communication brief or --raw-text")
                print(json.dumps({"status": "normalized", "brief": brief,
                                  "intent_sha256": intent_hash(brief)}, ensure_ascii=False, indent=2))
                return
            if args.command == "render":
                story = validate_native(validate(read(args.input)))
            else:
                story = write(args)
            if args.command != "write":
                print(json.dumps(render(args, story), indent=2))
        except NeedsInput as error:
            save(args.out / "result.json", error.result)
            print(json.dumps(error.result, indent=2))
        except UnsupportedBrief as error:
            result = {"status": "unsupported", "reason": str(error), "render_submitted": False}
            save(args.out / "result.json", result)
            print(json.dumps(result, indent=2))
        except CommunicationReview as error:
            result = {"status": "writer_refusal", "stage": "writing", "reason": str(error),
                      "render_submitted": False}
            save(args.out / "result.json", result)
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
