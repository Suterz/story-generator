"""Authored fallback designs for the frozen showcase, never autonomous scores."""

PAPER = "Warm cut-paper silhouettes and simple editorial cartoon staging, strong plum ink, soft ivory and rust accents, no decorative clutter."


def point(x, y):
    return [x / 100, y / 100]


def box(x1, y1, x2, y2, ink="ink"):
    return {"type": "shape", "shape": "rect", "at": point((x1 + x2) / 2, (y1 + y2) / 2),
            "extent": point(x2 - x1, y2 - y1), "ink": ink}


def ellipse(x, y, w, h, ink="accent"):
    return {"type": "shape", "shape": "disc", "at": point(x, y), "extent": point(w, h), "ink": ink}


def poly(*points, ink="ink"):
    return {"type": "shape", "shape": "polygon", "vertices": [point(*p) for p in points], "ink": ink}


def label(text, x=50, y=77, role="support"):
    return {"type": "text", "text": text, "at": point(x, y), "role": role}


def stroke(x1, y1, x2, y2, ink="ink", divisions=None):
    return {"type": "segment", "from": point(x1, y1), "to": point(x2, y2), "ink": ink,
            **({"divisions": divisions} if divisions else {})}


def outline(x1, y1, x2, y2, ink="ink"):
    return [stroke(x1,y1,x2,y1,ink), stroke(x2,y1,x2,y2,ink), stroke(x2,y2,x1,y2,ink), stroke(x1,y2,x1,y1,ink)]


def arrow(x1,y1,x2,y2):
    return {"type":"arrow", "from":point(x1,y1),"to":point(x2,y2)}


def person(x, y, ink="ink", bend=False):
    return [ellipse(x-2 if bend else x,y-18,10,5.6,"accent"),
            poly((x-6,y-15),(x+3,y-15),(x+7,y-5),(x-6,y-5),ink=ink),
            stroke(x-3,y-5,x-5,y,ink),stroke(x+3,y-5,x+6,y,ink)]


def three(slot, first, reveal, spoken, last=None):
    # Speech is an ordered list of (utterance, caption, optional pause). Two
    # or three panels share the accepted blank art and change exact overlays.
    if last is not None:
        spoken, last = last, spoken
    beats = [first, reveal] if last is None else [first, reveal, last]
    result = {"title": f"Morning review {slot}", "voice_profile": "heart", "max_ms": 29999,
              "visual": {"story_context": "A short standalone visual communication", "visual_signature": PAPER,
                         "graphic_theme": "paper"},
              "script": [], "beats": []}
    for i, (text, caption, *pauses) in enumerate(spoken):
        result["script"].append({"id": f"s{i}", "text": text, "caption": caption,
                                 **({"pause_after_ms": pauses[0]} if pauses else {})})
    for i, items in enumerate(beats):
        cue = {"ms": 0} if i == 0 else {"utterance_id": f"s{i}", "phrase": spoken[i][0].split(".")[0].split("?")[0]}
        panel = {"op": "new_scene" if i == 0 else "overlay_only", "scene_id": "scene",
                 "objective": "Make the given change and the stable reference visible on a phone",
                 "instruction": "Keep the exact authored flat shapes, placements, and readable labels",
                 "overlays": items, "retry_budget": 0}
        beat = {"id":f"b{i}", "cue":cue, "panel":panel}
        if i:
            beat["parent"] = f"b{i-1}"
        else:
            panel["paper_scene"] = True
        result["beats"].append(beat)
    return result


def library():
    back = [box(9,26,90,66,"pale"), box(18,35,47,66), box(22,38,43,66,"accent"),
            ellipse(39,51,3,1.6), box(62,46,84,49), stroke(9,67,90,67),
            label("ENTRANCE",33,70),label("RETURN SLOT",73,52)]
    book = poly((65,37),(79,37),(79,44),(65,44),ink="accent")
    inserted = [box(65,44,79,47,"accent"), arrow(72,56,72,48), label("SLIDE BOOK HERE",69,74)]
    return three("03",back+[book,label("AFTER HOURS",50,19,"value")],back+inserted,
                 [("Library dark? You can still return a book.","After-hours returns"),
                  ("Slide it into the return slot beside the entrance. The door stays closed.","Use the slot beside the entrance.")])


def pottery():
    cup = [poly((67,45),(79,45),(77,52),(69,52),ink="accent"),ellipse(79,47,6,3.4,"accent")]
    def drawing(active):
        return [box(14,57,44,61,"pale"),box(18,61,21,67),box(38,61,41,67),
                box(56,41,88,44),box(56,53,88,56),box(56,65,88,68),box(57,40,60,68),
                box(85,40,88,68),label("COUNTER",28,71),label("BLUE SHELF",72,71)] + (
                    cup+[arrow(46,48,58,51),label("TODAY",73,34,"value")] if active else [
                        poly((22,48),(36,48),(34,56),(24,56),ink="accent"),ellipse(36,50,6,3.4,"accent")])
    s=three("04",drawing(False),drawing(True),[
        ("Here to collect your pottery? We've moved pickup for today.","Pickup has moved"),
        ("Skip the counter. Your pottery is on the blue shelf.","Today: blue shelf")])
    s["visual"]["graphic_theme"]="atlas"
    return s


def bookmark():
    t=poly((18,53),(82,53),(50,35),ink="pale")
    pocket=poly((34,44),(66,44),(50,53),ink="accent")
    s=three("05",[t,stroke(18,53,82,53),arrow(50,35,50,50),label("LONG EDGE DOWN",50,68)],
                 [t,pocket,arrow(21,52,43,39),arrow(79,52,57,39),label("LIFT BOTH CORNERS",50,69)],
                 [poly((34,44),(50,35),(66,44),(50,53),ink="pale"),poly((34,44),(66,44),(50,35),ink="accent"),
                  stroke(34,44,66,44),arrow(43,36.5,43,43.5),arrow(57,36.5,57,43.5),label("TUCK INTO THE POCKET",50,73)],
                 [("Start with a folded triangle. Long edge down. Fold the front point down to make a pocket.","Fold the front layer down."),
                  ("Lift both bottom corners to the top point.","Lift both bottom corners."),
                  ("Tuck the two flaps into the pocket.","Tuck the flaps into the pocket.")])
    s["script"].append({"id":"s3","text":"Slide the bookmark onto a page corner.","caption":"Slip it onto the page corner."})
    final = {**s["beats"][-1]["panel"], "overlays":[box(24,26,76,65,"pale"), *outline(24,26,76,65),
            poly((24,26),(56,26),(24,44),ink="accent"),stroke(42,50,66,50),
            stroke(42,55,66,55),label("PAGE CORNER",50,72,"value")]}
    s["beats"].append({"id":"b3","parent":"b2","cue":{"utterance_id":"s3","phrase":"Slide the bookmark"},
                       "panel":final})
    return s


def crop():
    def draw(scale):
        # Render one source drawing through an unchanged viewport. Clip the
        # bench and its legs instead of changing their source geometry.
        u=lambda a: 50 + a*scale
        v=lambda a: 45 + a*scale*.5625
        shapes=[box(12,22,88,68,"pale")]
        for x1,y1,x2,y2 in ((-28,9,29,12),(-25,12,-22,23),(22,12,25,23),(-4,-2,4,9)):
            l,t,r,b=max(12,u(x1)),max(22,v(y1)),min(88,u(x2)),min(68,v(y2))
            if l<r and t<b:
                shapes.append(box(l,t,r,b))
        shapes.append(ellipse(u(0),v(-7),8*scale,4.5*scale))
        return shapes+outline(12,22,88,68)
    wide,tight=draw(1.25),draw(2.5)
    return three("06",wide+[label("WIDE CROP",50,68,"value")],tight+[label("TIGHT CROP",50,71,"value")],[
        ("In this wide crop, the bench and the person share the picture.","Wide: person and setting"),
        ("Crop in on the same photo. The bench stays, but the person fills more of the frame.","Tight: the person stands out")])


def board():
    grid=outline(25,30,75,62)+[stroke(50,30,50,62),stroke(25,46,75,46)]
    lower=[ellipse(37.5,54,13,7.3,"pale"),ellipse(62.5,54,13,7.3,"pale")]
    s = three("07",grid+lower+[ellipse(37.5,38,13,7.3,"accent"),ellipse(62.5,38,13,7.3,"ink"),label("SHARE AN EDGE",50,72)],
                 grid+lower+[ellipse(37.5,38,13,7.3,"ink"),ellipse(62.5,38,13,7.3,"accent"),label("TOP TWO SWAPPED",50,72,"value")],[
        ("In this game, swap two tokens only if their squares share an edge. Diagonal is out.","Share an edge."),
        ("Swap orange with its neighbor on the right. The lower row stays put.","Only the top two move.")])
    s["visual"]["graphic_theme"] = "atlas"
    return s


def bird(x,y):
    return [poly((x-11,y),(x-3,y-6),(x+8,y-5),(x+11,y+1),(x+1,y+4),ink="accent"),
            poly((x+8,y-5),(x+16,y-2),(x+10,y),ink="ink"),
            poly((x-7,y),(x-3,y-3),(x+3,y+1),ink="pale")]


def hopping():
    fixed = [stroke(10,60,90,60),label("SAME CAMERA",50,74)]
    s = three("08",fixed+bird(24,55)+[label("1",25,66)],fixed+bird(50,38)+[label("2",51,66)],
                 fixed+bird(73,55)+[label("3",74,66)],
                 [("Keep the camera still. Take one picture with the paper bird low.","First still: low"),
                  ("Move it forward and up for the next picture.","Second still: high"),
                  ("Then bring it down a little farther ahead.","Third still: low")])
    s["script"].append({"id":"s3","text":"Play them in order and the bird seems to hop.","caption":"Low, high, low."})
    final = {**s["beats"][-1]["panel"],
             "overlays":[stroke(10,60,90,60)]+bird(24,55)+bird(50,38)+bird(73,55)+
                        [label(str(i),x,66) for i,x in enumerate((24,50,73),1)]+[label("LOW · HIGH · LOW",50,76,"value")]}
    s["beats"].append({"id":"b3","parent":"b2","cue":{"utterance_id":"s3","phrase":"Play them in order"},"panel":final})
    return s


def poster():
    def card(large, small):
        # Same type treatment for both phrases. Near the safe margin, the
        # compositor fits the secondary phrase into a narrower local width.
        return [box(6,24,94,68,"pale")]+outline(6,24,94,68)+[
            label(large,50,37,"question"), label(small,20,57,"question")]
    return three("09",card("OPEN STUDIO","SATURDAY"),card("SATURDAY","OPEN STUDIO"),[
        ("Read this poster at a glance. What do you notice first?","What reads first?",900),
        ("The words haven't changed. Making Saturday larger shifts your eye from the event to the day.","Same words. Different emphasis.")])


def routes():
    back = [label("STATION",50,19), label("MUSEUM",50,70),
            stroke(50,23,26,31),stroke(26,31,26,58),stroke(26,58,50,65),
            stroke(50,23,73,31),stroke(73,31,73,58),stroke(73,58,50,65),
            label("GATE",26,38),label("4 MIN",26,44),label("20 STEPS",26,51),
            label("GARDEN",73,38),label("6 MIN",73,44),label("4 STEPS",73,51)]
    return three("10",back,back+[arrow(88,60,75,56),label("FEWER STAIRS",62,78,"value")],[
        ("Both routes go from the station to the museum. The gate is quicker, but has twenty steps.","Gate: 4 minutes, 20 steps."),
        ("Want fewer stairs? Take the garden path. Six minutes, just four steps.","Garden: 6 minutes, 4 steps.")])


def printfit():
    def objects(reveal):
        outer=outline(9,39,45,63.75)+outline(61,38,89,65)+[label("9 × 11",27,70),label("7 × 12",75,70)]
        if reveal:
            return [box(11,40,43,62.5,"accent"),box(59,40,91,62.5,"accent")]+outer+[label("SAME PRINT",50,26,"value")]
        return [box(34,18,66,40.5,"accent"),label("8 × 10 PRINT",50,13)]+outer
    return three("11",objects(False),objects(True),[
        ("This print is eight by ten. It has to lie flat. Which box fits?","Which box fits?",1000),
        ("See the same print in both outlines. Nine by eleven fits. Seven is too narrow, even with extra length.","Width matters as much as length.")])


def pause():
    art=[box(30,25,70,67,"ink"),box(34,28,66,67,"pale"),ellipse(61,49,4,2.25)]
    return three("12",art+[label("READING 1",50,17,"value")],art+[label("READING 2",50,17,"value")],[
        ("The door opened slowly.","The door opened slowly.",900),
        ("The door opened.","The door opened…",800),
        ("Slowly.","Slowly.")])


def shadow():
    art=[ellipse(16,46,14,8,"accent"),stroke(16,51,16,61), box(84,22,90,70,"pale"),
         label("LAMP",17,67),label("WALL",86,74)]
    outside=[stroke(22,44,84,24,"accent"),stroke(22,48,84,68,"accent")]
    return three("13",art+outside+[stroke(22,46,84,46,"accent")],
                 art+outside+[stroke(22,46,48,46,"accent"),box(48,39,53,53),box(84,31,90,61),
                  label("CARD",50,61),label("SHADOW",78,17,"value")],[
        ("Light from the lamp reaches the wall. Now put a card in its path.","Light reaches the wall."),
        ("Behind the card, some light cannot reach the wall. That's where the shadow comes from.","The card blocks part of the light.")])


PIXELS=((0,4),(1,3),(1,4),(2,2),(2,3),(3,1),(3,2),(4,1),(5,1),(6,2),(6,3),(7,3),(7,4))
def pixels():
    def draw(cx,cy,s):
        left=cx-4*s; top=cy-3*s*.5625
        return [box(left+x*s,top+y*s*.5625,left+(x+1)*s,top+(y+1)*s*.5625)
                for x,y in PIXELS]
    large=draw(50,49,8)
    for i in range(9):
        large.append(stroke(18+i*8,35.5,18+i*8,62.5,"accent"))
    for i in range(7):
        large.append(stroke(18,35.5+i*4.5,82,35.5+i*4.5,"accent"))
    return three("14",draw(50,47,1.8)+[label("SMALL IMAGE",50,65)],large+[label("SAME SQUARE STEPS",50,74,"value")],[
        ("From a distance, this arch looks curved. What's it made of?","Small view"),
        ("Zoom in. The edge is built from square steps. At small size your eye reads those steps together as a curve.","The same pixels, enlarged.")])


def tote():
    bag=[poly((24,36),(76,36),(72,64),(28,64),ink="pale"),
         stroke(33,36,39,26),stroke(39,26,61,26),stroke(61,26,67,36)]
    return three("15",bag+[stroke(47,49,53,52),stroke(53,52,46,56),label("A SMALL TEAR",50,72)],
                 bag+[box(41,46,58,59,"accent"),stroke(42,47,57,47,"ink",4),stroke(42,58,57,58,"ink",4),label("PATCH OVER THE TEAR",50,72,"value")],[
        ("Still reaching for that favorite tote? Don't give up on it for one small rip.","One small rip"),
        ("Cover the torn spot with a cloth patch. Fix the part that needs it, keep the bag you like.","Keep the bag you like.")])


def seed():
    table=[box(14,53,85,59,"pale"),box(22,59,27,69),box(72,59,77,69),label("WELCOME TABLE",50,68)]
    def pack(x,y):
        return [box(x-10,y-9,x+10,y+9,"accent"),poly((x-7,y-7),(x,y-2),(x+7,y-7),ink="pale"),
                label("BEANS",x,y+4)]
    return three("16",table+pack(33,36),table+pack(66,44)+[label("ONE LABELED PACKET",50,77,"value")],[
        ("First seed swap? You don't need a whole collection.","First seed swap?"),
        ("Bring one labeled packet to the welcome table. One is enough to get started.","One labeled packet.")])


def mitten(x,y,zig=True):
    return [poly((x-9,y+9),(x-10,y-2),(x-15,y-4),(x-12,y-8),(x-7,y-6),(x-7,y-11),
                 (x+6,y-11),(x+9,y-6),(x+8,y+9),ink="accent")]+(
        [stroke(x-5,y,x-1,y-3),stroke(x-1,y-3,x+2,y),stroke(x+2,y,x+6,y-3)] if zig else [ellipse(x,y-2,6,3.4,"ink")])


def lost():
    bench=[box(44,43,88,47),box(48,47,54,66),box(80,47,86,66)]
    return three("17",bench+mitten(22,50)+mitten(73,31,False),bench+mitten(22,50)+mitten(73,31,False)+mitten(66,59)+[arrow(48,73,61,61)],[
        ("One mitten. Where's the other? Not the one with the dot.","Which one matches?",1000),
        ("There. Same zigzag.","There. Same zigzag.")])


def chair():
    fixed=[stroke(8,70,91,70), box(51,54,73,58),box(51,37,55,54),box(52,58,55,68),box(70,58,73,68),
           box(14,54,36,58),box(14,37,18,54),box(15,58,18,68),box(33,58,36,68)]
    seated=[ellipse(25,40,10,5.6,"accent"),box(20,43,30,54),
            stroke(27,54,36,54),stroke(36,54,38,67)]
    guest=person(85,69)
    bag=lambda x,y:[box(x-8,y-10,x+8,y,"accent"),stroke(x-4,y-10,x,y-13),stroke(x,y-13,x+4,y-10)]
    guest_seated = [ellipse(61,41,10,5.6,"accent"), box(56,44,65,55),
                    stroke(63,55,71,55),stroke(71,55,73,66)]
    return three("18",fixed+seated+guest+bag(63,54),
                 fixed+seated+guest+bag(43,69)+[stroke(29,45,42,54),stroke(42,54,44,58)],
                 fixed+seated+guest_seated+bag(43,69),[
         ("There was one chair left. A bag sat on it.","One chair left, with a bag on it.",1000),
         ("Without a word.","Without a word.",950),
         ("Someone else sat down.","Someone else sat down.",1300)])


def postcard():
    def cup(x,y,s):
        w=s*10; h=s*5
        return [ellipse(x+w,y-h*.4,w*.62,h*.65,"ink"),poly((x-w,y-h),(x+w,y-h),(x+w*.75,y+h),(x-w*.75,y+h),ink="ink"),
                poly((x+w*.39,y-h),(x+w*.77,y-h),(x+w*.58,y-h*.54),ink="pale")]
    a=[box(13,30,87,66,"pale"),stroke(13,57,87,57),*cup(49,44,1.35),*person(22,57),*person(76,57)]
    b=[box(14,31,86,66,"pale")]+outline(14,31,86,66)+cup(40,48,1)+[stroke(63,34,63,61),box(71,36,80,41,"accent"),label("HOME",73,53)]
    sent=[box(27,41,73,69,"ink"),box(31,46,69,49,"accent"),
          box(34,29,66,47,"pale"),*cup(47,39,.83),box(59,32,63,35,"accent"),
          arrow(75,38,62,45)]
    s=three("20",a,b,sent,[
        ("Dad always gave me the blue cup. The chipped one, for tea at the kitchen table.","Dad gave me the chipped blue cup."),
        ("I drew that cup on a postcard for home.","I drew the cup on a postcard."),
        ("Some days, that's all I need to say: I miss you.","I miss you.")])
    s["visual"]["graphic_theme"]="atlas"
    return s


DESIGNS = {"03":library,"04":pottery,"05":bookmark,"06":crop,"07":board,"08":hopping,"09":poster,
           "10":routes,"11":printfit,"12":pause,"13":shadow,"14":pixels,"15":tote,"16":seed,"17":lost,
           "18":chair,"20":postcard}


def stage_art(lit=False):
    beams = [poly((48,22),(52,22),(78,65),(22,65),ink="pale")] if lit else []
    return [box(8,23,92,68,"ink"),box(13,26,87,61,"accent"),
            stroke(27,29,25,61),stroke(39,27,37,61),stroke(50,27,50,61),
            stroke(61,27,63,61),stroke(73,29,75,61),
            *beams,box(9,65,91,68),ellipse(50,21,7,3.9,"accent" if lit else "pale")]
