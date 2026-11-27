"""Bind parallel measurements to literal source rows before writing a comparison."""
import re

from daily import TEXT, array, ask, obj
from daily_evidence import persist

PROPERTIES = {
    "input": ("takes in", "receives", "consumes", "uses as input"),
    "return": ("returns", "gives back", "delivers as output"),
    "distance": ("travels", "covers"),
    "duration": ("takes", "lasts"),
    "cost": ("costs",),
    "yield": ("produces", "yields"),
    "mass": ("weighs",),
}
KNOWN_RATE_QUESTIONS = {
    frozenset(("input", "return")): "Which makes better use of its input?",
    frozenset(("distance", "duration")): "Which covers more distance per minute?",
    frozenset(("cost", "yield")): "Which costs less per usable unit?",
}
UNITS = {"kWh": "kilowatt-hours", "kW": "kilowatts", "km": "kilometers",
         "min": "minutes", "s": "seconds", "kg": "kilograms", "g": "grams",
         "L": "liters", "m": "meters", "USD": "dollars", "units": "units"}
PATTERN = re.compile(
    r"\b(?P<verb>" + "|".join(re.escape(v) for v in sorted(
        (x for forms in PROPERTIES.values() for x in forms), key=len, reverse=True)) +
    r")\s+(?P<value>\d+)\s+(?P<unit>" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\b",
    re.I,
)
VERBS = {v: p for p, variants in PROPERTIES.items() for v in variants}
SELECT = obj({"first": {"type": "integer"}, "second": {"type": "integer"},
              "hidden_property": {"enum": list(PROPERTIES)},
              "question": {**TEXT, "maxLength": 100}, "next_line": {**TEXT, "maxLength": 100}})


def literal_rows(sources):
    rows = []
    for passage in dict.fromkeys(sources):
        # This narrow adapter handles explicitly named, sentence-initial objects.
        # Unknown textual constructions remain unsupported instead of guessed.
        for sentence in re.split(r"(?<=[.!?])\s+", passage):
            matches = list(PATTERN.finditer(sentence))
            if not matches:
                continue
            entity = sentence[:matches[0].start()].strip()
            introduction = re.fullmatch(r"(?:Present|Show|Start with) (.+?) first:\s*it", entity, re.I)
            if introduction:
                entity = introduction[1]
            if not re.fullmatch(r"(?:[A-Za-z][\w-]*\s+){0,2}[A-Za-z][\w-]*", entity):
                continue
            previous = None
            for match in matches:
                conjunction = sentence[previous.end():match.start()].strip() if previous else ""
                if previous and conjunction not in ("and", ", and", "but", ", but"):
                    break
                unit = next(key for key in UNITS if key.casefold() == match["unit"].casefold())
                item = {"entity": entity, "property": VERBS[match["verb"].casefold()],
                        "value": int(match["value"]), "unit": unit, "source": sentence}
                if item not in rows:
                    rows.append(item)
                previous = match
    return rows


def spoken_integer(value):
    small = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
             "fifteen sixteen seventeen eighteen nineteen").split()
    tens = "twenty thirty forty fifty sixty seventy eighty ninety".split()
    if not 0 <= value < 1000:
        raise ValueError("opening number is outside the verified spoken integer range")
    if value < 20:
        return small[value]
    if value >= 100:
        head, tail = divmod(value, 100)
        return small[head] + " hundred" + (" " + spoken_integer(tail) if tail else "")
    head, tail = divmod(value, 10)
    return tens[head-2] + ("-" + small[tail] if tail else "")


def bind_selection(rows, decision, approved, *, neutral_question=False):
    indices = [decision["first"], decision["second"]]
    if any(not 0 <= i < len(rows) for i in indices):
        raise ValueError("opening selected an unknown source row")
    pair = [rows[i] for i in indices]
    if (pair[0]["entity"] == pair[1]["entity"] or
            (pair[0]["property"], pair[0]["unit"]) != (pair[1]["property"], pair[1]["unit"])):
        raise ValueError("opening selected different properties or units for the two objects")
    hidden = decision["hidden_property"]
    if hidden == pair[0]["property"] or not all(
            any(r["entity"] == item["entity"] and r["property"] == hidden for r in rows) for item in pair):
        raise ValueError("opening missing property is not a different sourced reading for both objects")
    question, next_line = decision["question"], decision["next_line"]
    extra = (question + " " + next_line).casefold()
    if not question.endswith("?") or re.search(r"\d|\b(wins|winner|correct answer|more efficient is)\b", extra):
        raise ValueError("opening needs an unanswered question and no extra numeric claims")
    if neutral_question:
        if not question.casefold().startswith("which "):
            raise ValueError("comparative prediction must use an unresolved 'Which …?' question")
        for item in pair:
            name = item["entity"]
            # Uppercase one-letter object IDs cannot be confused with lowercase articles.
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", question,
                         flags=0 if len(name) == 1 else re.I):
                raise ValueError("comparative question names a candidate instead of asking the viewer to choose")
    label = {"input": "Energy put in", "return": "Energy returned"}.get
    verb = PROPERTIES[pair[0]["property"]][0]
    lines = [f"{item['entity']} {verb} {spoken_integer(item['value'])} {UNITS[item['unit']]}."
             for item in pair] + [question, next_line]
    return {"promise": question, "states": [
        {"narration": line, "visible": "Two persistent objects; focus the current reading and leave the other property unknown.",
         "kind": "exact", "claim_ids": sorted(approved), "route_reason": "The viewer compares parallel measurements.",
         "visual_data": {"operation": "meters", "meters": [
             {"object": item["entity"], "readings": [
                 {"label": label(item["property"], item["property"].title()),
                  "display": f"{item['value']} {item['unit']}", "focus": index == side},
                 {"label": label(hidden, hidden.title()), "display": "?", "focus": False}]}
             for side, item in enumerate(pair)]}}
        for index, line in enumerate(lines)]}


def paired_options(rows):
    properties = {}
    for row in rows:
        key = row["entity"], row["property"]
        properties.setdefault(key, set()).add((row["unit"], row["value"]))
    if any(len(values) > 1 for values in properties.values()):
        raise ValueError("source has conflicting readings for one entity and property")
    options = []
    for i, first in enumerate(rows):
        for j, second in enumerate(rows[i+1:], i+1):
            if (first["entity"] == second["entity"]
                    or (first["property"], first["unit"]) != (second["property"], second["unit"])):
                continue
            hidden = ({(r["property"], r["unit"]) for r in rows if r["entity"] == first["entity"]}
                      & {(r["property"], r["unit"]) for r in rows if r["entity"] == second["entity"]})
            options.extend({"first": i, "second": j, "hidden_property": item}
                           for item, _ in sorted(hidden) if item != first["property"])
    return options


def bound_opening(endpoint, packet, approved, out, *, neutral_question=False, menu=False, rate_question=False):
    sources = [passage for row in approved.values() for passage in row["passages"]]
    rows = literal_rows(sources)
    persist(out / "source-measurements.json", rows)
    if len(rows) < 4:
        raise ValueError("source does not contain two verified parallel sets of measurements")
    instruction = ("Select two zero-based rows comparing the SAME property and unit across two "
                    "different objects. Prefer preserving source presentation order. Choose the other "
                    "property as hidden when its values are needed to answer. Ask the audience a concise "
                    "unanswered question. Follow it with a short direction about what to look for next. "
                    "Do not state the winner or speak additional numbers.")
    if neutral_question:
        instruction += (" Start the question with 'Which' and leave the answer unknown. "
                        "Never name either object in the question or ask why a specified object wins.")
    content = {"objective": packet["objective"], "rows": rows, "repair": packet.get("repair")}
    if menu:
        options = paired_options(rows)
        if not options:
            raise ValueError("source has no two compatible measurements and a shared missing property")
        schema = obj({"option": {"enum": list(range(len(options)))},
                      "question": SELECT["properties"]["question"], "next_line": SELECT["properties"]["next_line"]})
        content["comparison_options"] = options
        persist(out / "bound-options.json", options)
        instruction = ("Choose the zero-based comparison option that best serves the objective. The pair is "
                       "visible; its hidden_property remains unknown. Ask a short question starting 'Which' "
                       "whose answer REQUIRES the hidden property; don't ask which visible reading is higher or lower. "
                       "Don't name either object in the question. Give a very short next line about where to look.")
        chosen = ask(endpoint, instruction, content, schema, 520, out / "binding-response.json")
        selection = {**options[chosen["option"]], **chosen}
        if rate_question:
            pair = frozenset((rows[selection["first"]]["property"], selection["hidden_property"]))
            question = KNOWN_RATE_QUESTIONS.get(pair)
            if question:
                persist(out / "question-decision.json", {"writer_proposal": selection["question"],
                        "bound_question": question, "properties": sorted(pair)})
                selection["question"] = question
    else:
        selection = ask(endpoint, instruction, content, SELECT, 520, out / "binding-response.json")
    persist(out / "binding-selection.json", selection)
    return bind_selection(rows, selection, approved, neutral_question=neutral_question)
