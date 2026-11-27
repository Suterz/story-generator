"""Create a short, explicitly authored body regression pair on the same opening."""
import argparse
from pathlib import Path

from daily_evidence import persist
from opening_trial import compile_preview


def make(path, advancing):
    brief = {"topic": "Battery development body", "objective": "Pay off the opening comparison"}
    if advancing:
        states = [
            ("A takes in one hundred; B takes in sixty.", "Input, kWh", "100", "60"),
            ("Compare each return with its own input.", "Share returned", "75 / 100", "48 / 60"),
            ("B returns eight tenths. A returns three quarters. B used its input better.",
             "Share returned", "75%", "80%"),
        ]
    else:
        states = [
            ("A returned seventy-five; B returned forty-eight.", "Return, kWh", "75", "48"),
            ("A returned more. Its return was seventy-five.", "Return, kWh", "75", "48"),
            ("B returned less. Its return was forty-eight. A returned more.", "Return, kWh", "75", "48"),
        ]
    compiled = []
    for spoken, label, a, b in states:
        meters = [{"object": f"Battery {name}", "readings": [{"label": label, "display": value, "focus": False}]}
                  for name, value in (("A", a), ("B", b))]
        compiled.append({"narration": spoken, "visible": f"Both batteries show {label}", "kind": "exact",
                         "claim_ids": ["battery"], "visual_data": {"operation": "meters", "meters": meters}})
    path.mkdir(exist_ok=False)
    persist(path / "story.json", compile_preview(brief, {"promise": brief["objective"], "states": compiled},
                                                {"battery"}, "drama3-A"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    for label in ("repeated", "advancing"):
        make(args.root / label, label == "advancing")
