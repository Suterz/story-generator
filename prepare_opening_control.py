"""Development only: seed a daily/2 attempt with a known wrong-object focus."""
import argparse
import copy
from pathlib import Path

from daily_evidence import persist
from opening_trial import compile_preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    out = args.output
    attempt = out / "attempt-01"
    attempt.mkdir(parents=True, exist_ok=False)
    fact = ("Complete cycles at the same boundary. A takes in 100 kWh and returns 75 kWh. "
            "B takes in 60 kWh and returns 48 kWh. Efficiency is return divided by input.")
    brief = {"schema_version": "daily/2", "topic": "Which battery made better use of its input?",
             "audience": "Adults unfamiliar with energy efficiency",
             "objective": "Ask which system has higher efficiency. The spoken number must focus its own battery; "
                          "keep both inputs hidden in this opening.", "facts": [fact]}
    ledger = {"fact-1": {"claim": fact, "essential": True, "approved": [{"passage": fact}],
                         "route": "supplied", "decisions": []}}
    states = []
    for i, line in enumerate(("This battery returns seventy-five kilowatt-hours.", "This one returns forty-eight.",
                             "Which made better use of what went in?", "Look at each input before you decide.")):
        meters = [{"object": f"Battery {label}", "readings": [
                    {"label": "Energy returned", "display": f"{value} kWh", "focus": i == index},
                    {"label": "Energy put in", "display": "?", "focus": False}]}
                  for index, (label, value) in enumerate((("A", 75), ("B", 48)))]
        states.append({"narration": line, "visible": "Two stable batteries with returned readings and hidden inputs",
                       "kind": "exact", "claim_ids": ["fact-1"], "visual_data": {"operation": "meters", "meters": meters}})
    plan = {"promise": "Which battery uses input energy better?", "states": states}
    wrong = copy.deepcopy(plan)
    meters = wrong["states"][1]["visual_data"]["meters"]
    meters[0]["readings"][0]["focus"] = True
    meters[1]["readings"][0]["focus"] = False
    persist(out / "brief.json", brief)
    persist(out / "evidence.json", ledger)
    persist(out / "retrieval.json", [])
    persist(out / "expected-control.json", {"injected": "wrong-object focus in the second reading", "plan": plan})
    persist(attempt / "plan.json", wrong)
    persist(attempt / "story.json", compile_preview(brief, wrong, set(ledger), "drama3-A"))


if __name__ == "__main__":
    main()
