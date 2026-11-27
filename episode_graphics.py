"""Controlled evidence graphics. The writer selects states and their spoken cues."""
import json
from pathlib import Path


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
    if stage in ("reunion", "depart", "paths", "gps"):
        return twins(stage)
    if stage in ("speed", "one-year", "compare-years"):
        values = [text("CONSTANT SPEED: 0.99c", .19, role="value"),
                  *metric("Ship clock", "1 year", .34)]
        if stage != "speed":
            values += metric("Earth-frame time", "About 7.09 years", .55)
        if stage == "compare-years":
            values += [text("Both clocks work normally.", .77)]
        return values
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


def metric(label, value, y):
    return [rect(.5, y + .028, .83, .145), text(label, y),
            text(value, y + .057, role="value")]


def twins(stage):
    if stage == "gps":
        return [text("GPS CLOCKS", .16, role="value"),
                rect(.5, .47, .85, .43), dot([.50, .53]), dot([.21, .34]),
                line([.21,.34],[.50,.53]),
                text("Satellite", .30, .23), text("Earth", .60),
                text("Motion and gravity both matter", .75, role="value")]
    marks = [text("TWO TWINS", .14, role="value"), text("Earth twin", .23, .26),
             text("Traveling twin", .23, .74)]
    if stage == "paths":
        marks += [line([.38,.70],[.38,.34]), line([.38,.70],[.74,.51],"accent"),
                  line([.74,.51],[.38,.34],"accent"), dot([.38,.70]), dot([.38,.34]),
                  text("Turnaround", .46, .74),
                  text("Depart", .73, .38), text("Reunite", .30, .38)]
    else:
        for x, name in ((.26,"Stays"),(.74,"Travels")):
            marks += [rect(x,.45,.31,.31), {"type":"shape","shape":"disc","at":[x,.42],
                                           "extent":[.19,.106875],"ink":"ink"},
                      line([x,.42],[x,.381],"pale"),
                      line([x,.42],[x + (.046 if stage == "depart" or x < .5 else -.046),.42],"pale"),
                      text(name,.51,x),
                      text(("More elapsed" if x < .5 else "Less elapsed") if stage == "reunion" else "Clock agrees",.56,x)]
        marks += [text("Readings disagree" if stage == "reunion" else "Clocks start together", .71, role="value")]
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
CITATION_PACKET = Path(__file__).with_name("episodes") / "citation-source.json"
PASSAGES = {row["id"]: (row["population"], row["visible_lines"])
            for row in json.loads(CITATION_PACKET.read_text())["passages"]}


def citation(stage):
    if stage == "fiction":
        return [text("ILLUSTRATIVE FICTION", .19, role="question"), rect(.5,.45,.87,.35),
                text("M. Vale & R. Tern (2024)", .35, role="value"),
                text("The Shape of a Convincing", .43), text("Footnote", .47),
                text("Example Journal", .55), text("NOT A SOURCE", .72, role="question")]
    if stage in ("prompt", "tokens", "pattern"):
        marks = [text("Please pass the …", .29, role="value"), rect(.32,.54,.31,.14),
                 rect(.68,.54,.31,.14), text("salt",.54,.32), text("pepper",.54,.68)]
        return marks + [text({"prompt":"What comes next?", "tokens":"Pieces of text",
                              "pattern":"Likely wording is not evidence"}[stage], .71, role="question")]
    if stage == "habit":
        return [text("Check the particular claim", .19, role="value"),
                *metric("1", "Open the source", .32), *metric("2", "Find the passage", .51),
                *metric("3", "Compare its meaning", .70)]
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
