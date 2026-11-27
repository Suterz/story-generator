"""Find duplicated teaching passages without treating a static visual as a defect."""
from collections import Counter
import json
from pathlib import Path
import re
from fractions import Fraction

from daily import TEXT, array, obj, VISUAL

OUTLINE = obj({"hook": {"enum": ["prediction", "observation", "puzzle", "promise"]},
               "chapters": array(obj({"goal": {**TEXT, "maxLength": 140}, "visual": VISUAL,
                                      "new_inference": {**TEXT, "maxLength": 180}}), 3, 4)})
OUTLINE_DIRECTION = (
    "Each chapter must earn its place: state the inference a viewer can make only after this chapter. "
    "The second chapter must use the first chapter's result rather than teaching the same example again. "
    "Finish by applying the mechanism to a changed situation or answering the opening question. "
    "A useful still diagram may remain on screen. Do not extend runtime by restating facts."
)
AUTHOR_DIRECTION = (
    "Advance the stated new_inference. If a previously explained value is repeated, use it as an operand for "
    "a new inference, not a recap of the earlier comparison. Never repeat a previously spoken paragraph."
)


def comparison_support(claim, source, *, allow_ratio=False):
    """Use literal values only for a simple two-entity numeric comparison."""
    from opening_bindings import literal_rows

    match = re.fullmatch(r"(.+?) (returns|covers|costs|takes in) (more|less) (\w+) than (.+?)[.]?",
                         claim.strip(), flags=re.I)
    if not match:
        ratio = re.fullmatch(r"(.+?) has (higher|lower) round[- ]trip efficiency than (.+?)[.]?",
                             claim.strip(), flags=re.I)
        absolute = re.fullmatch(r"(.+?)(?:'s|’s) round[- ]trip efficiency is (\d+(?:\.\d+)?)%[.]?",
                                claim.strip(), flags=re.I)
        if not allow_ratio or not (ratio or absolute) or not re.search(
                r"efficiency is returned energy divided by input energy", source, re.I):
            return None
        entities = (ratio[1], ratio[3]) if ratio else (absolute[1],)
        rows = literal_rows([source])
        readings = []
        for entity in entities:
            values = [{(r["value"], r["unit"]) for r in rows if r["entity"].casefold() == entity.casefold()
                       and r["property"] == prop} for prop in ("return", "input")]
            if not all(len(v) == 1 for v in values):
                return None
            (returned, r_unit), (input_, i_unit) = (next(iter(v)) for v in values)
            if r_unit != i_unit or input_ <= 0:
                return None
            readings.append(Fraction(returned, input_))
        if ratio:
            supported = readings[0] > readings[1] if ratio[2].lower() == "higher" else readings[0] < readings[1]
        else:
            supported = readings[0] * 100 == Fraction(absolute[2])
        return "supports" if supported else "contradicts"
    a, verb, relation, unit, b = match.groups()
    prop = {"returns": "return", "covers": "distance", "costs": "cost", "takes in": "input"}[verb.lower()]
    rows = literal_rows([source])
    values = [{row["value"] for row in rows if row["entity"].casefold() == entity.casefold()
               and row["property"] == prop and row["unit"].casefold() == unit.casefold()} for entity in (a, b)]
    if not all(len(value) == 1 for value in values):
        return None
    left, right = (next(iter(value)) for value in values)
    supported = left > right if relation.lower() == "more" else left < right
    return "supports" if supported else "contradicts"


def rate_evidence(passages):
    """Compute parallel ratios from source operands, retaining exact fractions."""
    from opening_bindings import literal_rows

    rows = literal_rows(passages)
    families = (("return", "input"), ("distance", "duration"), ("cost", "yield"))
    results = {}
    for top, bottom in families:
        for entity in dict.fromkeys(row["entity"] for row in rows):
            candidates = [{(r["value"], r["unit"]) for r in rows
                           if r["entity"] == entity and r["property"] == prop} for prop in (top, bottom)]
            if not all(len(c) == 1 for c in candidates):
                continue
            (n, n_unit), (d, d_unit) = map(lambda items: next(iter(items)), candidates)
            if d <= 0:
                continue
            key = f"{top}/{bottom} ({n_unit}/{d_unit})"
            results.setdefault(key, []).append({"entity": entity, "numerator": n, "denominator": d,
                                                 "exact_rate": str(Fraction(n, d))})
    return results

def duplicated(chapters):
    from storygen import words

    seen = {}
    problems = []
    for chapter, sections in enumerate(chapters, 1):
        for section in sections["sections"]:
            words_ = words(section["narration"])
            if len(words_) >= 12:
                key = " ".join(words_)
                old = seen.setdefault(key, chapter)
                if old != chapter:
                    problems.append({"chapter": chapter, "repeats_chapter": old, "kind": "verbatim_passage"})
    return problems


def audit(attempt):
    story = json.loads((attempt / "story.json").read_text())
    media = json.loads((attempt / "manifest.json").read_text())
    decode = json.loads((attempt / "decoded-review.json").read_text())
    starts = set(story["chapter_starts"])
    beats = {row["id"]: row["seconds"] for row in decode["cues"]}
    panels = {row["id"]: row["sha256"] for row in media["panels"]}
    speech = json.loads((attempt / "delivered-track.json").read_text())["asr"]
    chapters, intervals = [], []
    durations = Counter()
    for i, row in enumerate(story["script"]):
        key = row["id"]
        start = beats[key]
        end = beats[story["script"][i+1]["id"]] if i+1 < len(story["script"]) else decode["duration"]
        if key in starts:
            chapters.append({"sections": []})
        delivered = "".join(word["word"] for word in speech if start <= (word["start"]+word["end"])/2 < end)
        chapters[-1]["sections"].append({"narration": row["text"]})
        durations[panels[key]] += end-start
        intervals.append({"id": key, "chapter": len(chapters), "start": start, "end": end,
                          "panel_sha256": panels[key], "delivered": delivered})
    caption_frames = sum(x["end_frame"]-x["start_frame"] for x in media["caption_trace"] if x.get("text", "").strip())
    frames = media["verification"]["expected_video_frames"]
    return {"duration": decode["duration"], "duplicate_authored_passages": duplicated(chapters),
            "identical_panel_seconds": dict(durations), "caption_frame_fraction": caption_frames/frames,
            "intervals": intervals}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    print(json.dumps(audit(parser.parse_args().attempt), indent=2))
