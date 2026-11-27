"""Compare frozen development arms after reading the separate archive labels."""
import argparse
from pathlib import Path

from daily_evidence import persist
from storygen import read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("predictions", "label_key", "guided", "automatic", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--reveal-witnesses", type=Path)
    args = parser.parse_args()
    labels = read(args.label_key)
    guided = read(args.guided)["rows"]
    automatic = read(args.automatic)
    reveal = read(args.reveal_witnesses) if args.reveal_witnesses else {}
    comparisons = {}
    versions = ["ordinary-observation", "source-derived", "indexed-source",
                "ordinary-plus-automatic", "evaluator-guided"]
    if reveal:
        versions.append("ordinary-plus-automatic-and-visual-reveal")
    for name in versions:
        cases = []
        for case, label in sorted(labels.items()):
            version = name if name in ("source-derived", "indexed-source") else "ordinary-observation"
            path = args.predictions / case / f"{version}.json"
            if not path.exists():
                continue
            row = read(path)
            if row["mp4_sha256"] != guided[case]["mp4_sha256"] or row["mp4_sha256"] != automatic[case]["mp4_sha256"]:
                raise ValueError(f"{case}: development arms don't bind to the same MP4")
            verdict = row["status"]
            automatic_arm = name.startswith("ordinary-plus-automatic")
            fault = (automatic[case]["faults"] or [None])[0] if automatic_arm else guided[case]["fault"]
            if name == "ordinary-plus-automatic-and-visual-reveal" and case in reveal:
                witness = reveal[case]
                if witness["mp4_sha256"] != row["mp4_sha256"]:
                    raise ValueError(f"{case}: reveal evidence binds to different media")
                if not witness["seen_at_first_mention"] and "$" in witness["printed_diagram_observation"]:
                    fault = {"code": "early_reveal", "start_seconds": witness["first_spoken_seconds"],
                             "detail": "The embargoed answer is spoken while the diagram still withholds it.",
                             "scope": "development rule requiring visual concurrence"}
            if (automatic_arm or name == "evaluator-guided") and fault:
                verdict = "failed"
            else:
                fault = None
            # A local quote is not automatically a diagnosis. Only explicit
            # assertion code and timing can be compared mechanically here.
            expected = guided[case]["fault"]
            localized = bool(fault and expected and fault["code"] == expected["code"]
                             and abs(fault["start_seconds"]-expected["start_seconds"]) <= 1.0)
            cases.append({"case": case, "label": label, "status": verdict, "local_result": row,
                          "timed_assertion": fault, "localization_matches_control": localized})
        comparisons[name] = {"sample": len(cases), "bad_total": sum(c["label"] == "bad" for c in cases),
                             "good_total": sum(c["label"] == "good" for c in cases),
                             "bad_accepted": sum(c["label"] == "bad" and c["status"] == "accepted" for c in cases),
                             "good_withheld": sum(c["label"] == "good" and c["status"] != "accepted" for c in cases),
                             "assertion_localizations": sum(c["localization_matches_control"] for c in cases),
                             "cases": cases}
    persist(args.output, {"purpose": "reused development cases, no independent qualification", "arms": comparisons})


if __name__ == "__main__":
    main()
