"""Source-approved editorial inputs for the flagship release, not scripts."""
from pathlib import Path

from storygen import read


def chapter(question, claims, *stages):
    return {"question": question, "chapter_claims": claims, "stages": [list(stage) for stage in stages],
            "words": "115–140 (around 40 per visual state)"}


def assemble():
    base = read(Path(__file__).with_name("development") / "decisive.json")
    a, b, c = (dict(item, schema_version="episode/1", min_ms=180000) for item in base)
    a["sources"]["A2"] = "https://doi.org/10.12942/lrr-2003-1"
    a["editorial_direction"] = ("Open on two reunited twins with disagreeing working clocks. Both started together. "
                                "Return to this exact mystery at the end. Earth times are synchronized coordinate "
                                "measurements, not the light delay to one eye.")
    a["chapters"] = [
        chapter("How can two good clocks disagree?",
                ["Fictional reunion; both clocks ran normally and were together at departure and return.",
                 "Compare elapsed time, not a clock fault or light-travel delay."],
                ("reunion","Show both working clocks."),
                ("depart","Return to synchronized departure."), ("reunion","Return to the disagreement.")),
        chapter("What makes a tick?",
                ["A full tick is lower mirror to upper mirror and back.",
                 "Follow only emission E to reflection R, a half-tick; not the proper time of a photon."],
                ("ship","Use the straight four-unit path in the labeled ship frame."),
                ("shift","Treat the moving mirror as a question before drawing the pulse.")),
        chapter("Where does the upper mirror actually meet that pulse?", a["claims"], *a["stages"]),
        chapter("How large can that difference be?",
                ["Switch from the diagram's 0.6c to a different constant-speed leg at 0.99c.",
                 "At 0.99c one ship year corresponds to about 7.09 Earth-frame years, not a whole round trip.",
                 "The traveler feels normal. Say the decimal in words."],
                ("speed","Show the ship year and new speed."),
                ("one-year","Compare with the Earth-frame years."),
                ("compare-years","Emphasize that both clocks behave normally.")),
        chapter("Why does the result not cancel at reunion?",
                ["At turnaround the traveling twin changes inertial frames; the two worldlines between the same endpoint events differ.",
                 "The travelers' clocks record their own elapsed time. GPS accounts for motion and gravity; no numeric GPS claim.",
                 "Return to the meaning of the reunited clocks after GPS."],
                ("paths","Trace the two paths and common endpoints."),
                ("gps","Brief application to satellite clock rates."),
                ("reunion","Pay off the question of the two clocks.")),
    ]
    b["sources"]["B2"] = "https://www.bankofengland.co.uk/explainers/how-is-money-created"
    b["editorial_direction"] = ("Open just before a fictional $100,000 loan is booked. Follow the same borrower and seller. "
                                "Never imply saved cash is passed to the borrower; dollars are illustrative, not a national regulation claim.")
    b["chapters"] = [
        chapter("When a bank credits the account, what else does it write?",
                ["Approval is not origination. At origination Bank A creates a matching loan asset and new deposit liability.",
                 "Explain who owes whom and that no other customer's deposit falls."],
                ("before","Show before the transaction."),
                ("origination","Post the two entries together."), ("wealth","See the borrower’s side.")),
        chapter("Is the borrower a hundred thousand dollars richer?",
                ["The spendable deposit and debt offset at origination without fees. Money and wealth are not the same.",
                 "The deposit is an asset of the borrower and a liability of Bank A."],
                ("origination","Show Bank A’s two entries."), ("wealth","Show matching borrower asset and debt.")),
        chapter("Does the loan follow the payment?", b["claims"], *b["stages"]),
        chapter("Why can't the bank do this without limit?",
                ["Interbank settlement uses reserves, which the bank must obtain and manage.",
                 "Capital absorbs losses. Creditworthiness, profitability and demand constrain lending.",
                 "Policy interest rates influence costs and demand without a fixed loan result."],
                ("settlement","Make the reduced A reserves inspectable."),
                ("limits","Hold the bank figures while distinguishing liquidity and other limits."),
                ("outstanding","Return to why the lender cares about the existing loan.")),
        chapter("What disappears when the borrower repays principal?",
                ["Use separate, pre-existing $1,000 savings at Bank A. These savings were not the spent deposit.",
                 "Pay down principal only: savings fall by $1,000 and Bank A loan falls from $100,000 to $99,000; B's seller deposit and reserves unchanged.",
                 "Interest is a distinct charge/income flow, not principal reduction. End by returning to the original two entries."],
                ("outstanding","Before repayment, locate the original loan."),
                ("repayment","Show the $99,000 result and savings source.")),
    ]
    c["sources"]["C1"] = "https://arxiv.org/abs/2509.04664"
    c["editorial_direction"] = ("Investigate rather than scold. Keep the fictional reference visibly fictional from the first frame. "
                                "When using the real document, distinguish the question, passage and generated answer.")
    c["chapters"] = [
        chapter("Which part of a convincing-looking reference shows anyone checked the paper?",
                ["Illustrative fictional citation M. Vale and R. Tern, The Shape of a Convincing Footnote, Example Journal, 2024. No fake DOI.",
                 "A predictable format is not proof of a source being verified."],
                ("fiction","Open on the fictional card."), ("prompt","Offer a familiar completion."),
                ("tokens","Name ordinary pieces of text.")),
        chapter("What does predicting likely wording tell us about truth?",
                ["A token is a piece of text; next-token pretraining learns patterns.",
                 "Fluent wording is not calibrated certainty; later training and tools affect behavior.",
                 "No made-up measured probabilities or universal error rates."],
                ("prompt","Return to a familiar completion."), ("pattern","Separate likely wording from factual evidence."),
                ("fiction","Return to the plausible pattern of the fictional citation.")),
        chapter("What can we learn from the actual GPT-4 passage?", c["claims"],
                ("source","Open Walters and Wilder's real document."),
                ("support","Read the scoped GPT-4 result: 18 percent among its cited works in this study.")),
        chapter("Can the right paper still be the wrong evidence?", c["claims"],
                ("source","Keep the exact GPT-4 question."),
                ("mismatch","Expose the GPT-3.5 passage without moving the question."),
                ("reject","Explain why the group mismatch defeats the claim.")),
        chapter("What should a viewer actually do next time?",
                ["Open source, locate passage, compare meaning with particular claim.",
                 "Search locates candidates; a calculator checks inputs and arithmetic, not source meaning.",
                 "A search failure does not establish a work never existed. Refer back to the fictional card."],
                ("fiction","Recall the opening question."), ("habit","Give the three-step action.")),
    ]
    return a, b, c
