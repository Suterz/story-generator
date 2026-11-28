"""Production brief and teachable-order preflight, shared by batch intake and runs."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

TEXT = {"type": "string", "minLength": 1, "maxLength": 3000}


def obj(properties, required=None):
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties) if required is None else required}


def array(items, minimum=0, maximum=16):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


def digest(brief):
    return hashlib.sha256(json.dumps(brief, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


ID = {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,63}$"}
ITEM = obj({"id": ID, "description": TEXT, "must_show": TEXT, "requires": array(ID),
            "establishes": array(ID, 1), "evidence_ids": array(ID, 1)})
EVIDENCE = obj({"id": ID, "claim": TEXT, "kind": {"enum": ["supplied", "hypothetical", "public_gap"]},
                "source": TEXT}, ["id", "claim", "kind"])
BRIEF = obj({"schema_version": {"const": "daily/3"}, **dict.fromkeys(
                ("topic", "audience", "prior", "objective", "takeaway", "tone"), TEXT),
             "intro": ITEM, "lesson": ITEM, "mechanism": array(ITEM, 1, 8), "result": ITEM,
             "transfer": obj({"question": TEXT, "answer": TEXT, "reasoning": TEXT}),
             "facts": array(EVIDENCE, 1), "constraints": array(TEXT),
             "defaults": {"const": "portrait-education-v1"},
             "duration": obj({"kind": {"enum": ["target", "hard"]},
                              "min_seconds": {"type": "integer", "minimum": 20, "maximum": 300},
                              "max_seconds": {"type": "integer", "minimum": 20, "maximum": 300}}),
             "comparison": obj({"unit": TEXT, "objects": array(obj({
                 "name": TEXT, "input": {"type": "integer", "minimum": 1},
                 "returned": {"type": "integer", "minimum": 0}}), 2, 2),
                 "answer": TEXT, "evidence_id": ID})},
            ["schema_version", "topic", "audience", "prior", "objective", "takeaway", "tone",
             "intro", "lesson", "mechanism", "result", "transfer", "facts", "defaults", "duration"])


def stages(brief):
    return [brief["intro"], brief["lesson"], *brief["mechanism"], brief["result"]]


def inspect(brief):
    receipt = {"brief_sha256": digest(brief), "policy": "lesson-readiness-v1",
               "status": "ready", "issues": [], "defaults": "portrait-education-v1",
               "queueable": False, "execution_route": None}

    def add(field, reason, status="needs_input"):
        receipt["issues"].append({"field": field, "reason": reason})
        # Unresolved caller intent takes precedence over a researchable gap.
        order = ("ready", "needs_research", "needs_input", "withhold")
        if order.index(status) > order.index(receipt["status"]):
            receipt["status"] = status

    errors = sorted(Draft202012Validator(BRIEF).iter_errors(brief), key=lambda e: str(list(e.path)))
    for entry in errors:
        location = list(map(str, entry.path))
        if entry.validator == "required":
            missing = re.match(r"'([^']+)' is a required property", entry.message)
            if missing:
                location.append(missing[1])
        add("/" + "/".join(location), entry.message)
    if errors:
        return receipt
    for field in ("topic", "audience", "prior", "objective", "takeaway", "tone"):
        value = brief[field].strip().casefold().strip(".")
        if not value or value in {"everyone", "general", "none", "tbd", "whatever", "interesting", "something"}:
            add(f"/{field}", "provide the audience knowledge, teaching decision or explicit preference")
    objective = brief["objective"].strip()
    objective_action = re.search(r"\b(compare|predict|calculate|identify|distinguish|describe how|"
                                 r"explain (?:how|why|when|which)|determine|apply|interpret|evaluate)\b",
                                 objective, re.I)
    if not objective_action:
        add("/objective", "state what the viewer will compare, predict, calculate, or explain and under which conditions")
    if brief["duration"]["min_seconds"] > brief["duration"]["max_seconds"]:
        add("/duration", "minimum duration exceeds maximum", "withhold")
    if brief["transfer"]["question"].strip() == brief["transfer"]["answer"].strip():
        add("/transfer", "supply an independently checkable answer to the changed case")
    if not all(brief["transfer"][k].strip() for k in ("question", "answer", "reasoning")):
        add("/transfer", "supply a changed case, expected answer and reasoning")
    if not brief["transfer"]["question"].rstrip().endswith("?"):
        add("/transfer/question", "ask an explicit question about a changed case")
    evidence = {row["id"]: row for row in brief["facts"]}
    if len(evidence) != len(brief["facts"]):
        add("/facts", "duplicate evidence IDs", "withhold")
    for row in evidence.values():
        if row["kind"] == "public_gap":
            add("/facts/" + row["id"], "resolve this public claim before production: " + row["claim"], "needs_research")
        elif row["kind"] == "supplied" and not row.get("source", "").strip():
            add("/facts/" + row["id"], "supplied factual claim needs a source")
    seen, ids = set(), set()
    for stage in stages(brief):
        at = "/stages/" + stage["id"]
        if stage["id"] in ids:
            add(at, "duplicate phase ID", "withhold")
        ids.add(stage["id"])
        for field in ("description", "must_show"):
            if stage[field].strip().casefold() in {"", "tbd", "show a diagram", "show evidence", "make interesting"}:
                add(at + "/" + field, "specify what the viewer must understand or see")
        if missing := set(stage["requires"]) - seen:
            add(at, "teaching prerequisites are not established yet: " + ", ".join(sorted(missing)), "withhold")
        if not set(stage["establishes"]) - seen:
            add(at, "phase establishes no new inference")
        elif set(stage["establishes"]) & seen:
            add(at, "phase claims to establish an inference already established")
        if missing := set(stage["evidence_ids"]) - evidence.keys():
            add(at, "undefined evidence: " + ", ".join(sorted(missing)), "withhold")
        seen.update(stage["establishes"])
    if compare := brief.get("comparison"):
        objects = compare["objects"]
        values = [Fraction(row["returned"], row["input"]) for row in objects]
        if len({r["name"] for r in objects}) != 2 or compare["evidence_id"] not in evidence:
            add("/comparison", "two distinct objects and a valid evidence ID are required", "withhold")
        expected = "tie" if values[0] == values[1] else objects[values.index(max(values))]["name"]
        if expected != compare["answer"]:
            add("/comparison/answer", f"supplied winner conflicts with exact ratios: expected {expected}", "withhold")
        if ("ratios_shown" not in brief["result"]["requires"]
                or "inputs_revealed" not in brief["lesson"]["establishes"]):
            add("/result/requires", "ratio comparison must depend on worked ratios and explicit input evidence", "withhold")
        if grounding := evidence.get(compare["evidence_id"]):
            rows = grounding["claim"]
            unit = re.escape(compare["unit"])
            for item in objects:
                expected_line = (rf"\b{re.escape(item['name'])}\s+takes in\s+{item['input']}\s+{unit}"
                                 rf"\s+and returns\s+{item['returned']}\s+{unit}\b")
                # Only the first compiler's supported literal source form is
                # admitted. Other forms should get another adapter, not guessed values.
                if grounding["kind"] != "public_gap" and not re.search(expected_line, rows, re.I):
                    add("/comparison", f"readings for {item['name']} are not bound to its stated source sentence",
                        "withhold")
        whole_percent = all((value*100).denominator == 1 and 0 <= value <= 1 for value in values)
        names_fit = all(re.fullmatch(r"[A-Za-z][A-Za-z ]{0,18}", row["name"]) for row in objects)
        if (compare["unit"] == "kWh" and whole_percent and names_fit and len(brief["mechanism"]) == 1
                and "ratios_shown" in brief["mechanism"][0]["establishes"]
                and max(max(row["input"], row["returned"]) for row in objects) < 1000):
            receipt["execution_route"] = "exact-return-ratio"
        else:
            receipt["execution_route"] = None
    else:
        receipt["execution_route"] = None
    receipt["queueable"] = receipt["status"] == "ready" and receipt["execution_route"] is not None
    return receipt


def validate_brief_file(path):
    brief = json.loads(path.read_text())
    report = inspect(brief)
    if not report["queueable"]:
        detail = "; ".join(f"{e['field']}: {e['reason']}" for e in report["issues"][:4])
        raise ValueError(f"{path.name}: {report['status']}; {detail or 'no supported execution route'}")
    return report


def plan_errors(brief, plan):
    """Expected facts are read from the brief, never inferred from the rendered plan."""
    expected = {row["id"]: row for row in stages(brief)}
    seen, completed = set(), set()
    errors = []
    for row in plan:
        sid = row["id"]
        if sid not in expected:
            errors.append(f"{sid}: no matching approved phase")
            continue
        if sid in completed:
            errors.append(f"{sid}: repeated phase")
        spec = expected[sid]
        if missing := set(spec["requires"]) - seen:
            errors.append(f"{sid}: conclusion before evidence: {', '.join(sorted(missing))}")
        if not set(row["establishes"]) <= set(spec["establishes"]):
            errors.append(f"{sid}: introduces an unapproved inference")
        if set(row["establishes"]) != set(spec["establishes"]):
            errors.append(f"{sid}: does not establish the required inference")
        seen.update(row["establishes"])
        completed.add(sid)
    if missing := expected.keys()-completed:
        errors.append("missing phases: " + ", ".join(sorted(missing)))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    result = ([{"topic": row.get("topic") if isinstance(row, dict) else None, **inspect(row)} for row in data]
              if isinstance(data, list) else inspect(data))
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    temporary = args.out.with_suffix(".partial")
    temporary.write_text(text)
    temporary.replace(args.out)
    print(text, end="")


if __name__ == "__main__":
    main()
