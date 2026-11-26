"""Translate an authored exact count row into ordinary renderer overlays."""


COUNTER_ROW = {
    "type": "object",
    "properties": {
        "count": {"type": "integer", "minimum": 1, "maximum": 12},
        "id": {"type": "string"},
        "y": {"type": "number", "minimum": .22, "maximum": .65},
        "label": {"type": "string"},
    },
    "required": ["count", "id", "y", "label"],
    "additionalProperties": False,
}


def expand_counter_rows(panel):
    rows = panel.pop("counter_rows", [])
    if not rows:
        return
    if len(rows) > 3 or any(abs(a["y"] - b["y"]) < .11 for i, a in enumerate(rows) for b in rows[i+1:]):
        raise ValueError("counter rows need separate vertical space")
    if sum(row["count"] + 1 for row in rows) > 23:
        raise ValueError("too many visible items for a phone-sized count lesson")
    graphics = panel.setdefault("overlays", [])
    for row in rows:
        count, y = row["count"], row["y"]
        if type(count) is not int or not 1 <= count <= 12 or not .22 <= y <= .65:
            raise ValueError("invalid counter count or row position")
        step = min(.11, .72 / max(1, count - 1))
        width = step * .61
        for i in range(count):
            x = .50 + (i - (count - 1)/2) * step
            graphics.append({"type": "shape", "shape": "disc", "at": [x, y], "ink": "accent",
                             "extent": [width, width * 9 / 16], "fact": f"{row['id']}-{i + 1}"})
        graphics.append({"type": "text", "text": row["label"], "at": [.50, y + .048],
                         "role": "support", "fact": f"{row['id']}-label"})
