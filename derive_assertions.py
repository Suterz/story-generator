"""Narrow executable assertions inferred from explicit relational source language."""
import argparse
import re
from pathlib import Path

from daily_evidence import persist
from opening_assertions import observed_assertion
from storygen import read

DOLLARS = r"\$(\d{1,3}(?:,\d{3})+|\d+)"
SMALL = dict(zip("one two three four five six seven eight nine".split(), range(1, 10), strict=True))


def derive(source, objective):
    """No inspection windows, expected defect labels or topic switches."""
    checks = []
    # Match a source explicitly naming the remaining money values. The generic
    # runtime rule is triggered by a spoken remaining-salaries assertion only.
    for sentence in re.split(r"(?<=[.!?])\s+", source):
        if re.search(r"\b(leaves|removed)\b.*\bonly\b.*\bremain\b", sentence, re.I):
            retained = re.search(r"\bonly\b(.+?)\bremain\b", sentence, re.I)
            values = sorted(int(s.replace(",", "")) for s in re.findall(DOLLARS, retained[1]))
            if values and re.search(r"\b(payroll|salaries)\b", objective, re.I):
                checks.append({"kind": "listed_values", "subject": "the remaining salaries",
                               "expected": values, "source_quote": sentence})
        steady = re.search(r"\bnumber (waiting) stays at (\w+)\b", sentence, re.I)
        if steady and (steady[2].isdigit() or steady[2].casefold() in SMALL):
            number = int(steady[2]) if steady[2].isdigit() else SMALL[steady[2].casefold()]
            # Preserve the source's stated time scope; the runtime finds the
            # spoken state marker, not a human-labeled seconds interval.
            sequence = re.search(r"between (minutes?) (\w+) and (\w+)", objective, re.I)
            if sequence:
                checks.append({"kind": "count_transition", "subject": "people " + steady[1].lower(),
                               "expected": [number, number], "source_quote": sentence,
                               "spoken_scope": f"minute {sequence[3].lower()}"})
    return checks


def search(words, rule):
    if not words:
        return None
    scan = words
    if scope := rule.get("spoken_scope"):
        target = scope.split()
        aliases = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five"}
        normalized = [row["word"].strip().casefold().strip(".,!?;:") for row in words]
        starts = [i for i in range(len(words)-1) if normalized[i] == target[0]
                  and aliases.get(normalized[i+1], normalized[i+1]) == target[1]]
        if not starts:
            return None
        scan = []
        for start in starts:
            end = next((i for i in range(start+2,len(words)-1) if normalized[i] == target[0]
                        and (normalized[i+1] in SMALL or normalized[i+1].isdigit())), len(words))
            fault = search(words[start:end], {k: v for k, v in rule.items() if k != "spoken_scope"})
            if fault:
                return fault
        return None
    return observed_assertion(scan, {**rule, "interval": [scan[0]["start"], scan[-1]["end"]+.01]})


def rewind_witness(source, objective, words, frames):
    """Affirm only the rewind relation; it cannot clear a later contradiction."""
    if not re.search(r"\brewind\b", objective, re.I):
        return None
    original = re.search(r"\boriginal roster ([^.]+)", source, re.I)
    if not original:
        return None
    values = {int(x.replace(",", "")) for x in re.findall(DOLLARS, original[1])}
    if len(values) < 2:
        return None
    for i, word in enumerate(words):
        if word["word"].strip(" .,!?").lower() != "rewind":
            continue
        subsequent = words[i:i+32]
        if "original" not in "".join(w["word"] for w in subsequent).casefold():
            continue
        for frame in frames:
            if not word["start"] <= frame["seconds"] <= subsequent[-1]["end"]+1:
                continue
            text = frame["observed"]
            seen = {int(x.replace(",", "")) for x in re.findall(DOLLARS, text)}
            seen |= {int(x)*1000 for x in re.findall(r"\$(\d+)k\b", text, re.I)}
            if values <= seen:
                return {"relation": "original roster restored during explicit spoken rewind",
                        "spoken_start_seconds": word["start"], "decoded_sample_seconds": frame["seconds"],
                        "source_values": sorted(values), "observation": text}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("packets", "observations", "output"):
        parser.add_argument(key, type=Path)
    args = parser.parse_args()
    rows = {}
    specs = {}
    for case in sorted(args.packets.iterdir()):
        packet = read(case / "packet.json")
        specs[case.name] = {"mp4_sha256": packet["mp4_sha256"], "checks": derive(packet["evidence"], packet["objective"])}
    args.output.mkdir(exist_ok=False)
    persist(args.output / "derived-before-observations.json", specs)
    from opening_score import sha

    for case, spec in specs.items():
        if sha(args.packets / case / "video.mp4") != spec["mp4_sha256"]:
            raise ValueError(f"{case}: immutable MP4 changed")
        words = read(args.observations / case / "actual-words.json")
        faults = [found for check in spec["checks"] if (found := search(words, check))]
        packet = read(args.packets / case / "packet.json")
        frames = read(args.observations / case / "sampled-observations.json")
        witness = rewind_witness(packet["evidence"], packet["objective"], words, frames)
        rows[case] = {**spec, "faults": faults, "rewind_witness": witness,
                      "state": "contradiction" if faults else "not_established"}
    persist(args.output / "results.json", rows)


if __name__ == "__main__":
    main()
