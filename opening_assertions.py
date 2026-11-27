"""Inspect timed spoken claims without asking a reviewer to infer from the picture."""
import re

from opening_review import early_quantity, heard_numbers


def observed_assertion(words, rule, *, origin=0):
    kind = rule["kind"]
    if kind == "numeric_embargo":
        return early_quantity(words, rule["quantity"], rule["through"], origin=origin)
    if kind not in ("count_transition", "listed_values"):
        raise ValueError(f"unknown opening observation rule: {kind}")
    start, stop = rule["interval"]
    spans = [row for row in words if start <= origin+row["start"] < stop]
    for i, row in enumerate(spans):
        window = spans[i:i+18]
        text = " ".join(w["word"].strip().casefold() for w in window)
        if kind == "count_transition":
            # Anchor the claim to its explicit comparative language.
            number = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine)"
            phrase = f" {rule['subject']} instead of "
            match = re.match(rf"{number}{re.escape(phrase)}{number}\b", text)
            if not match:
                continue
            names = dict(zip("one two three four five six seven eight nine".split(), range(1, 10), strict=True))
            front, back = match[0].split(phrase)
            to_int = lambda value: int(value) if value.isdecimal() else names[value]
            current, prior = to_int(front), to_int(back)
            if [prior, current] == rule["expected"]:
                continue
            detail = f"Delivered statement '{match[0]}' gives {prior} → {current}, expected {rule['expected']}."
        else:
            match = re.match(re.escape(rule["subject"]) + r" (?:are|were) (.+?)[.!?]", text)
            if not match:
                continue
            amounts = re.sub(r"(?<=\d)\s*,\s*(?=\d{3}\b)", "", match[1])
            found = sorted(heard_numbers(amounts))
            if not found or found == rule["expected"]:
                continue
            detail = f"Delivered statement '{match[0]}' names {found}, expected {rule['expected']}."
        return {"status": "failed", "code": "wrong_value", "start_seconds": origin+row["start"],
                "detail": detail, "repair": "Correct the delivered statement to the independently sourced values."}
    return None
