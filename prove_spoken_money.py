"""Technical controls for speech notation; these aren't scored brief outputs."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from storygen import SKILL, compile_story, read, save
from spoken_money import normalize_story_money


def main():
    endpoint, directory = sys.argv[1:]
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    for name, first, second in (("two-prices", "$1.60", "$2.00"), ("small-change", "$0.05", "$3.01")):
        folder = root / name
        folder.mkdir(exist_ok=True)
        request = read(SKILL.parent / "annotated-example.json")
        request["title"] = "Read both amounts"
        request["voice_profile"] = "heart"
        request["script"][0]["text"] = "Two prices are on the cards."
        request["script"][1].update(text="Which card costs less?", caption="Which card costs less?")
        request["script"][2]["text"] = f"The first card costs {first}. The second card costs {second}."
        request["instructional"].pop("spoken_answer_phrases")
        overlays = [{"type": "text", "at": [.5, y], "text": amount, "role": "value", "fact": key}
                    for y, amount, key in ((.38,first,"first-price"),(.54,second,"second-price"))]
        request["beats"][0]["panel"].update(overlays=overlays, instruction="Draw the exact prices.")
        last = deepcopy(overlays)
        last.append({"type":"text","at":[.5,.70],"text":"FIRST CARD COSTS LESS","role":"support"})
        request["beats"][-1]["panel"].update(overlays=last, instruction="Keep both exact prices and mark the lower one.")
        save(folder/"printed-request.json", request)
        compiled = compile_story(normalize_story_money(request))
        save(folder/"story.json", compiled)
        status = subprocess.run([sys.executable,"-B",str(SKILL.parents[3]/"storygen.py"),"render",
                                 str(folder/"story.json"),"--out",str(folder),"--video-url",endpoint],
                                check=False)
        if status.returncode:
            raise SystemExit(status.returncode)
        result=read(folder/"outcome.json")
        print(name,result["state"],result.get("error",""),flush=True)


if __name__ == "__main__":
    main()
