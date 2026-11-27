"""Exact visual fixtures for the transfer episodes."""
import json
import math
from pathlib import Path

from episode_graphics import arrow, dot, line, metric, rect, text


def polygon(points, ink="accent"):
    return {"type": "shape", "shape": "polygon", "vertices": points, "ink": ink}


def disc(x, y, w, ink="pale"):
    return {"type": "shape", "shape": "disc", "at": [x, y], "extent": [w, w * 9 / 16], "ink": ink}


def seasons(stage):
    marks = [text("SOUTHERN COMPARISON · 45° S" if stage == "south" else "MINNEAPOLIS · ABOUT 45° N",
                  .12, role="value")]
    if stage in ("orbit", "axis"):
        marks += [disc(.50,.47,.20,"accent"), text("Sun",.56),
                  disc(.20,.47,.16), disc(.80,.47,.16),
                  line([.15,.56],[.25,.38]), line([.75,.56],[.85,.38]),
                  text("June",.62,.20), text("December",.62,.80),
                  text("Same axis direction",.73,role="question")]
        return marks
    if stage == "south":
        return marks + [*metric("June at 45° S", "Shorter day; lower noon Sun", .29),
                        *metric("December at 45° S", "Longer day; higher noon Sun", .54)]
    if stage.startswith("day"):
        for y, label, ratio in ((.30, "June: longer daylight", .65), (.54, "December: shorter daylight", .35)):
            marks += [text(label,y),rect(.5,y+.065,.76,.043,"ink"),
                      rect(.12 + .38*ratio,y+.065,.76*ratio,.043,"accent"),
                      text("One full rotation",y+.11)]
        return marks
    for y, label, angle in ((.38, "June · 68.5°", 68.5), (.65, "December · 21.5°", 21.5)):
        theta = math.radians(angle)
        x = .58 - .30 * math.cos(theta)
        v = y - .30 * math.sin(theta) * 9 / 16
        marks += [line([.22,y],[.79,y]), arrow([x,v],[.58,y]), text(label,y+.055)]
    return marks + [text("Idealized solar-noon angles",.80)]


ARRIVALS = ((0, "A"), (1, "B"), (1, "C"), (2, "D"))


def queue_at(minute, delayed=False):
    events = [(3 if delayed and label == "D" else t, label) for t, label in ARRIVALS]
    active, end, waiting, done = None, None, [], []
    for now in range(minute + 1):
        if now == end:
            done.append(active)
            active = end = None
        if active is None and waiting:
            active, end = waiting.pop(0), now + 2
        waiting.extend(label for t, label in events if t == now)
        if active is None and waiting:
            active, end = waiting.pop(0), now + 2
    return active, waiting, done


def queue(stage):
    minute = {"rules":0, "first":0, "arrivals":1, "prediction":1, "second":2, "delay":2,
              "next":4, "drain":8}[stage]
    active, waiting, done = queue_at(minute, stage == "delay")
    marks = [text(f"MINUTE {minute}",.15,role="value"), text("2 minutes per service",.22),
             *metric("At the counter",active or "Nobody",.32),
             *metric("Waiting in order"," → ".join(waiting) or "Nobody",.51),
             text("Departed: " + (", ".join(done) if done else "none"),.77)]
    if stage in ("rules","first","arrivals","prediction"):
        marks += [text("Arrivals: A at 0; B and C at 1; D at 2",.71)]
    if stage == "delay":
        marks += [text("New case: D arrives at minute 3",.71)]
    return marks


def percent(stage):
    marks = [text("THE BASE CHANGES", .14, role="value"), *metric("Starting price","$100",.26)]
    if stage != "base":
        marks += metric("20% of $100 is $20","$80 after the drop",.44)
    if stage in ("up","both","restore"):
        marks += metric("20% of $80 is $16","$96 after the rise",.62)
    if stage == "restore":
        marks += [text("$20 ÷ $80 = 25% to get back",.80,role="question")]
    return marks


def shutter(stage):
    marks = [text("SAME CAMERA · SAME SPEED",.14,role="value"),text("1,000 image pixels per second",.20)]
    cases = ((.36,100,10),(.62,25,40)) if stage != "short" else ((.36,100,10),)
    for y, denom, span in cases:
        x = .28
        width = span * .011
        marks += [text(f"Exposure: 1/{denom} second",y-.06),line([.18,y],[.84,y]),
                  dot([x,y]), dot([x+width,y]),rect(x+width/2,y+.065,width,.027,"accent"),
                  text(f"{span} px of travel",y+.12)]
    return marks


def study(stage):
    marks = [text("EXACT QUESTION",.13,role="question"),text("How soon did an assessment",.19),
             text("attempt count after viewing?",.23),rect(.5,.49,.86,.40)]
    if stage in ("review","mismatch"):
        marks += [text("Brame · Reviewing Guo et al.",.33,role="value"),
                  text("“They observed that the median",.41),
                  text("engagement time for videos",.455),
                  text("less than 6 minutes long was",.50),
                  text("close to 100%”",.545)]
        if stage == "mismatch":
            marks += [text("Relevant study; different measure",.65,role="question")]
    elif stage in ("method","answer"):
        marks += [text("Guo et al. · Measuring Engagement",.33,role="value"),
                  text("“whether a student attempted",.41),
                  text("to answer the follow-up problem",.455),
                  text("within 30 minutes after",.50,role="value"),
                  text("watching a video”",.545)]
        if stage == "answer":
            marks += [text("Supports the 30-minute definition",.65,role="question")]
    else:
        marks += [text("Two genuinely related documents",.43)]
    return marks


def project(lon, lat, mode):
    lam, phi = math.radians(lon + 48), math.radians(lat)
    if mode == "globe":
        center = math.radians(16)
        return [.50 + .41 * math.cos(phi) * math.sin(lam),
                .48 - .41 * 9/16 * (math.cos(center)*math.sin(phi) -
                                    math.sin(center)*math.cos(phi)*math.cos(lam))]
    scaled = math.asinh(math.tan(phi)) if mode == "mercator" else math.sin(phi)
    return [.50 + .29*lam,.56 - .29 * 9/16 * scaled]


def map_view(stage):
    mode = {"globe":"globe","mercator":"mercator","patches":"mercator","equal-area":"equal-area"}[stage]
    outlines = json.loads((Path(__file__).with_name("episodes") / "coastlines.json").read_text())
    marks = [text({"globe":"GLOBE VIEW", "mercator":"SPHERICAL MERCATOR",
                   "equal-area":"CYLINDRICAL EQUAL-AREA"}[mode], .07, role="value")]
    if mode == "globe":
        marks += [disc(.5,.48,.82,"pale")]
    for name, ink in (("greenland","accent"),("south-america-mainland","ink")):
        marks += [polygon([project(x,y,mode) for x,y in outlines[name]],ink)]
    if stage == "patches":
        # Equal small angular areas require a wider longitude extent at 60°.
        # Both patches have equal spherical area: width * delta(sin(latitude)).
        phi0, phi1 = -3, 3
        target = math.sin(math.radians(phi1)) - math.sin(math.radians(phi0))
        width = 6 * target / (math.sin(math.radians(63)) - math.sin(math.radians(57)))
        for lat, span in ((0,6),(60,width)):
            x0, x1 = -6-span/2, -6+span/2
            marks += [polygon([project(x0,lat-3,mode),project(x1,lat-3,mode),
                               project(x1,lat+3,mode),project(x0,lat+3,mode)],"pale")]
            marks += [text("Equator" if lat == 0 else "60° N", project(-6,lat,mode)[1], .83)]
        marks += [text("Patches have equal area on Earth",.73,role="support")]
    marks += [text("Greenland / South America",.80)]
    return marks


def salary(stage):
    people = [("A",40),("B",60),("C",80)]
    if stage in ("leave","after","transfer"):
        people = people[1:]
    marks = [text("ANNUAL PAY · FICTIONAL ROSTER",.12,role="value")]
    for i,(name,pay) in enumerate(people):
        y = .27 + i*.13
        marks += [text(name,y,.19,role="question"),rect(.49,y,pay*.005,.047),
                  text(f"${pay},000",y,.52)]
    if stage != "roster":
        marks += metric(f"Total ${sum(p for _,p in people)},000 ÷ {len(people)}",
                        f"Mean ${sum(p for _,p in people)//len(people)},000",.66)
    return marks


TRANSFER_RENDERERS = {"seasons":seasons,"queue":queue,"percent":percent,"shutter":shutter,
                      "study":study,"map":map_view,"salary":salary}
