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
    a["chapters"][0]["stage_claims"] = {
        "reunion": ["The reunited twins compare two clocks that ran normally. One measured less time.",
                    "Ask how two working clocks disagree. Do not answer yet."],
        "depart": ["At their common departure the clocks were synchronized. One twin stays on Earth and one travels.",
                   "The twin feels normal. No claims about seeing tick speeds during the trip in this chapter."],
    }
    a["chapters"][3]["stage_claims"] = {
        "speed": ["This is a new demonstration: ninety-nine percent of the speed of light.",
                  "Show a one year reading on the ship for this constant-speed leg. Earth number is still hidden."],
        "one-year": ["Ninety-nine percent of light speed, exactly as shown. One year on ship; about seven point zero nine years of Earth-frame time."],
        "compare-years": ["Both clocks work normally. The traveler does not feel slowed.",
                          "The example is for one constant-speed leg, not the full trip."],
    }
    a["chapters"][1]["stage_claims"] = {
        "ship": ["One full tick is the pulse from the lower mirror to the upper mirror and back to the lower mirror.",
                 "The highlighted four-unit upward path is only the first half-tick, from emission E to reflection R."],
        "shift": ["In the Earth frame the ship moves only sideways between those same two events.",
                  "The upper mirror is no longer over E when light arrives. Do not describe the length of the diagonal before showing it."],
    }
    a["chapters"][2]["stage_claims"] = {
        "ship": ["The same pulse travels upward from emission E at the lower mirror to reflection R at the upper mirror in the ship frame. Four units."],
        "shift": ["The whole ship shifts three units sideways in Earth's frame between emission and reflection.",
                  "The new upper-mirror position is marked R. Save the complete light path for the next visual."],
        "path": ["The diagonal leaves E and arrives at R at the new upper mirror position; five units versus four in the ship.",
                 "Both frames measure the same light speed. Earth therefore assigns more time to this same half-tick, emission to reflection."],
    }
    a["chapters"][4]["stage_claims"] = {
        "paths": ["Both worldlines start and end together. The traveler changes inertial frame at turnaround.",
                  "The elapsed proper time differs along the two paths. Do not infer elapsed time from drawn Euclidean line lengths."],
        "gps": ["Relative to the comparison clock on Earth, the effect of satellite motion is to slow its clock.",
                "The weaker gravity at GPS orbital altitude makes the satellite clock run faster.",
                "These effects do not exactly cancel. GPS accounts for both. No drift numbers are needed."],
        "reunion": ["Return to the clocks: elapsed time is what each clock accumulated along its own path.",
                    "Neither clock malfunctioned; the two different readings are compatible."],
    }
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
                ("savings","Before repayment, locate the original loan and separate savings."),
                ("repayment","Show the $99,000 result and savings source.")),
    ]
    b["chapters"][0]["stage_claims"] = {
        "before": ["Loan and new transaction deposit are zero at the start; the seller deposit is zero too.",
                   "The loan has not been originated. Ask what will go on both sides."],
        "origination": b["chapters"][0]["chapter_claims"],
        "wealth": ["Borrower deposit and borrower debt both increase by one hundred thousand dollars.",
                   "The deposit is the bank's liability; the debt is the borrower's liability."],
    }
    b["chapters"][1]["stage_claims"] = {
        "origination": ["Describe which entries are Bank A's asset and liability. Asset: borrower owes Bank A on its loan. Liability: Bank A owes borrower the spendable deposit."],
        "wealth": ["The borrower can spend the new deposit. Matching debt cancels its initial net-wealth gain. Introduce the question of paying a customer who uses a different bank."],
    }
    b["chapters"][2]["stage_claims"] = {
        "origination": ["Immediately before payment: new borrower deposit at A is $100,000; seller deposit at B is zero. The buyer pays the seller."],
        "settlement": ["Borrower deposit at Bank A falls to zero; seller gets deposit of $100,000 at B.",
                       "A transfers $100,000 in central-bank reserves to B to settle. A reserves $20,000; B reserves $120,000."],
        "outstanding": ["Bank A still owns the unchanged $100,000 loan asset. The borrower still owes A, but their new deposit at A is now zero.",
                        "The seller can spend a deposit at B, not spend reserves. Contrast the two different kinds of balances."],
    }
    b["chapters"][3]["stage_claims"] = {
        "settlement": ["The reserve outflow shows why the bank needs settlement liquidity and funding. The bank cannot promise to settle an unlimited amount."],
        "limits": ["Capital absorbs losses. Separate it from reserves used for settlement. Banks evaluate ability to repay, risk, and profitability."],
        "outstanding": ["Bank A still owns the loan and bears its credit risk. Creditworthy borrowers must want loans; policy rates influence funding costs, rates and demand without a fixed result."],
    }
    b["chapters"][4]["stage_claims"] = {
        "savings": ["The borrower owes Bank A the original $100,000. Separately, the borrower has $1,000 of pre-existing savings at Bank A. That's where the repayment funds are held."],
        "repayment": ["A reduces the borrower's savings deposit by $1,000 and the loan by $1,000 to $99,000. Both at A; no reserves move and B's deposit does not change.",
                      "This is principal only. Interest is a separate bank income flow, not principal. Return to creation at origination."],
    }
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
    c["chapters"][0]["stage_claims"] = {
        "fiction": ["The displayed citation is invented and explicitly labeled illustrative, not a source.",
                    "Formatting does not tell us anyone checked it. Leave the mechanism unanswered."],
        "prompt": ["Use exactly the example shown: ‘Please pass the …’, with salt and pepper as plausible continuations."],
        "tokens": ["A token is a piece of text, often a word or part of a word. This is illustrative, not a measured distribution."],
    }
    c["chapters"][1]["stage_claims"] = {
        "prompt": ["Use the salt and pepper example. Several next pieces of text can fit the same words."],
        "pattern": ["Next-token pretraining learns patterns of language; it does not itself prove any given fact. Fluency is not a calibrated probability that the claim is true."],
        "fiction": ["A model can reproduce the pattern of a reference without evidence for this particular paper. Later training and tools affect behavior."],
    }
    c["chapters"][2]["stage_claims"] = {
        "source": ["Open Walters and Wilder's real study. Ask what fraction of GPT-4 citations in that study were fabricated. The link alone does not settle it."],
        "support": ["The GPT-4 paragraph says only eighteen percent are fabricated. This is about cited works in the study's GPT-4 sample, not all answers or other models."],
    }
    c["chapters"][3]["stage_claims"] = {
        "source": ["Keep the same GPT-4 sample question, but compare a nearby related passage that cites a different population."],
        "mismatch": ["The displayed paragraph is about GPT-3.5. Of the two hundred and twenty-two works cited in the GPT-3.5 papers, fifty-five percent were fabricated."],
        "reject": ["The result says nothing about the GPT-4 group's percentage. State what it does support and abstain from giving a GPT-4 number from this paragraph alone."],
    }
    return a, b, c
