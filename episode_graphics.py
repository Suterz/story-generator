"""Controlled evidence graphics. The writer selects states and their spoken cues."""


def text(value, y, x=.5, role="support"):
    return {"type": "text", "text": value, "at": [x, y], "role": role}


def line(a, b, ink="ink"):
    return {"type": "segment", "from": a, "to": b, "ink": ink}


def rect(x, y, w, h, ink="pale"):
    return {"type": "shape", "shape": "rect", "at": [x, y], "extent": [w, h], "ink": ink}


def dot(p, ink="accent"):
    return {"type": "shape", "shape": "disc", "at": p, "extent": [.022, .012375], "ink": ink}


def arrow(a, b):
    return {"type": "arrow", "from": a, "to": b}


def light_events(origin, horizontal, separation=4, unit=.105):
    x, y = origin
    return [x, y], [x + horizontal * unit, y - separation * unit * 9 / 16]


def clock(stage):
    ship_e, ship_r = light_events((.39, .42), 0)
    earth_e, earth_r = light_events((.39, .76), 3)
    earth_start_upper = light_events(earth_e, 0)[1]
    def mirror(point, ink="ink"):
        return rect(point[0], point[1], .14, .015, ink)
    marks = [
        text("SHIP FRAME", .12, role="value"),
        mirror(ship_e), mirror(ship_r),
        line(ship_e, ship_r, "accent"), dot(ship_e), dot(ship_r),
        text("E", .42, .25), text("R", .184, .25),
        text("4 units", .302, .67),
        text("EARTH FRAME", .49, role="value"),
        mirror(earth_e), mirror(earth_start_upper),
        dot(earth_e), text("E", .76, .25),
    ]
    if stage in ("shift", "path"):
        end_lower = [earth_r[0], earth_e[1]]
        marks += [mirror(earth_r), mirror(end_lower), dot(earth_r), text("R", .524, .84),
                  arrow([.41, .792], [.685, .792]), text("3 sideways", .815)]
    if stage == "path":
        marks += [line(earth_e, earth_r, "accent"), text("5 units", .66, .68)]
    return marks


OPENING_LEDGER = {
    "A": {"reserves": 120_000_00, "loan": 0, "new deposit": 0, "savings": 1_000_00,
          "other": 99_000_00, "equity": 20_000_00},
    "B": {"reserves": 20_000_00, "loan": 0, "new deposit": 0, "savings": 0,
          "other": 15_000_00, "equity": 5_000_00},
}
EVENTS = (
    {"A": {"loan": 100_000_00, "new deposit": 100_000_00}},
    {"A": {"reserves": -100_000_00, "new deposit": -100_000_00},
     "B": {"reserves": 100_000_00, "new deposit": 100_000_00}},
    {"A": {"loan": -1_000_00, "savings": -1_000_00}},
)


def ledger_at(count):
    accounts = {bank: values.copy() for bank, values in OPENING_LEDGER.items()}
    for event in EVENTS[:count]:
        for bank, changes in event.items():
            for account, amount in changes.items():
                accounts[bank][account] += amount
    if any(a["reserves"] + a["loan"] != a["new deposit"] + a["savings"] + a["other"] + a["equity"]
           or min(a.values()) < 0 for a in accounts.values()):
        raise ValueError("unbalanced ledger")
    return accounts


def money(cents):
    return f"${cents // 100:,}"


def bank(stage):
    count = {"before": 0, "origination": 1, "wealth": 1, "settlement": 2,
             "outstanding": 2, "limits": 2, "repayment": 3}[stage]
    accounts = ledger_at(count)
    marks = [text({"origination": "THE LOAN IS MADE", "settlement": "THE SELLER IS PAID",
                   "outstanding": "THE LOAN STAYS PUT", "before": "BEFORE THE LOAN",
                   "wealth": "DEPOSIT AND DEBT", "limits": "BANK A STILL HAS TO SETTLE",
                   "repayment": "PRINCIPAL REPAID"}[stage], .12, role="value")]
    marks += [rect(.28, .44, .44, .48), rect(.72, .44, .43, .48), line([.5, .20], [.5, .68])]
    for bank_id, x, customer in (("A", .285, "Borrower"), ("B", .716, "Seller")):
        a = accounts[bank_id]
        marks += [text(f"BANK {bank_id}", .24, x, "question"),
                  text(f"{customer} deposit", .38, x), text(money(a["new deposit"]), .43, x, "value"),
                  text("Reserves", .53, x), text(money(a["reserves"]), .58, x, "value")]
        if bank_id == "A":
            marks += [text("Loan asset", .29, x), text(money(a["loan"]), .333, x, "value")]
    if stage == "settlement":
        marks += [arrow([.29, .72], [.71, .72]), text("$100,000 in reserves", .77)]
    if stage == "outstanding":
        marks += [text("Borrower still owes Bank A", .75, role="question")]
    if stage == "wealth":
        marks += [text("Borrower: +$100,000 deposit", .72), text("and +$100,000 debt", .77)]
    if stage == "repayment":
        marks += [text("Bank A savings: $1,000 to $0", .73), text("Principal only", .78)]
    return marks


PAPER = "Walters & Wilder (2023)"
QUERY = "GPT-4 citations: what share\nwere fabricated in this sample?"
PASSAGES = {
    "mismatch": ("GPT-3.5", ("Of the 222 works cited in", "the GPT-3.5 papers,", "55% are fabricated.")),
    "support": ("GPT-4", ("The vast majority of GPT-4", "citations refer to works that", "are verifiably real.", "Only 18% are fabricated.")),
}


def citation(stage):
    marks = [text("QUESTION", .13, role="question")]
    marks += [text(s, .18 + i * .045) for i, s in enumerate(QUERY.splitlines())]
    marks += [rect(.5, .475, .88, .39), text(PAPER, .315, role="value"),
              text("Results / Extent of fabrication", .36)]
    if stage == "source":
        return marks + [text("PAPER OPEN", .52, role="question"), text("Scientific Reports", .575)]
    group, exhibit = PASSAGES["mismatch" if stage in ("mismatch", "reject") else "support"]
    marks += [text(group, .42, role="question")]
    marks += [text(s, .465 + i * .044) for i, s in enumerate(exhibit)]
    if stage == "reject":
        marks += [text("Wrong group for this claim", .72, role="value")]
    if stage == "support":
        marks += [text("18% in this study's GPT-4 sample", .72, role="support")]
    return marks


RENDER = {"spatial": clock, "worked-example": bank, "source-verification": citation}
