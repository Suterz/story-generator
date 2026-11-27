"""Make opaque development-generated candidates for independent human screening.

There are no publishability labels in this package. A controlled alteration
is known to the preparer; a human must still label the entire delivered clip.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont

CASES = (
    ("Rain gauges", "Which garden got more rain?", "North", "South", 14, 21, "millimeters"),
    ("Seed packets", "Which packet produced more seedlings?", "Packet A", "Packet B", 18, 12, "seedlings"),
    ("Cooling cups", "Which cup cooled by more?", "Cup A", "Cup B", 7, 11, "degrees"),
    ("Bike lights", "Which light ran longer?", "Light A", "Light B", 16, 22, "minutes"),
    ("Walking routes", "Which route is longer?", "Canal", "Park", 6, 9, "kilometers"),
    ("Tile measurements", "Which tile is wider?", "Clay", "Stone", 25, 18, "centimeters"),
    ("Porch shade", "Which spot had more shade?", "East", "West", 12, 15, "minutes"),
    ("Toy wheels", "Which wheel made more turns?", "Red", "Blue", 8, 13, "turns"),
    ("Water bottles", "Which bottle holds more?", "Tall", "Wide", 4, 6, "liters"),
    ("Workshop scales", "Which bag is heavier?", "Bag A", "Bag B", 15, 17, "kilograms"),
    ("Bird counts", "Which garden had more visits?", "Gate", "Pond", 14, 19, "visits"),
    ("Solar readings", "Which panel delivered more energy?", "Panel A", "Panel B", 12, 18, "kilowatt-hours"),
)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def frame(path, topic, names, numbers, unit, focused, obscured=False):
    image = Image.new("RGB", (360, 640), "#faf6ed")
    draw = ImageDraw.Draw(image)
    for value, size, position in ((topic, 24, (180, 125)), (unit, 16, (180, 375))):
        draw.text(position, value, font=ImageFont.truetype(FONT, size), fill="#202c37", anchor="mm")
    for i, (name, number) in enumerate(zip(names, numbers, strict=True)):
        x = 14 + i*174
        fill = "#ffe0a6" if focused == i else "white"
        draw.rounded_rectangle((x, 194, x+158, 344), 12, fill=fill, outline="#314d5c", width=2)
        ink = "#fff7e7" if obscured and i == 1 else "#202c37"
        draw.text((x+79, 232), name, font=ImageFont.truetype(FONT, 17), fill="#202c37", anchor="mm")
        draw.text((x+79, 290), str(number), font=ImageFont.truetype(FONT, 34), fill=ink, anchor="mm")
    image.save(path)


def main():
    from video_renderer.voice_profiles import synthesize
    import soundfile

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.output
    screen = root / "blind"
    secure = root / "private"
    screen.mkdir(parents=True, exist_ok=False)
    secure.mkdir(mode=0o700)
    home = Path.home()
    ffmpeg = str(home / "ai/tools/media/bin/ffmpeg")
    model = home / "ai/storyboard-rehearsal/fresh/speech/models/heart"
    rows = []
    for index, (topic, question, a, b, x, y, unit) in enumerate(CASES):
        common = secure / str(index)
        common.mkdir()
        lines = [f"{a} measured {x} {unit}.", f"{b} measured {y} {unit}.",
                 f"{question} Take a moment to compare the readings."]
        recordings, rate = synthesize("heart", model, lines)
        durations = [len(recording)/rate for recording in recordings]
        for i, recording in enumerate(recordings):
            soundfile.write(common / f"{i}.wav", recording, rate, subtype="PCM_16")
        with wave.open(str(common / "combined.wav"), "wb") as assembled:
            assembled.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            for i in range(3):
                with wave.open(str(common / f"{i}.wav")) as source:
                    assembled.writeframes(source.readframes(source.getnframes()))
        for changed in (False, True):
            opaque = secrets.token_hex(6)
            unsafe = ("wrong_value", "wrong_object", "illegible")[index % 3] if changed else None
            images = common / opaque
            images.mkdir()
            numbers = (x, y+2) if unsafe == "wrong_value" else (x, y)
            for i in range(3):
                focus = 0 if i == 1 and unsafe == "wrong_object" else i
                frame(images / f"{i}.png", topic, (a,b), numbers, unit, focus, unsafe == "illegible")
            concat = images / "frames.txt"
            concat.write_text("".join(f"file '{i}.png'\nduration {t:.6f}\n" for i, t in enumerate(durations))
                              + "file '2.png'\n")
            case = screen / opaque
            case.mkdir()
            clip = case / "video.mp4"
            subprocess.run([ffmpeg, "-v", "error", "-f", "concat", "-i", str(concat),
                            "-i", str(common / "combined.wav"), "-map", "0:v:0", "-map", "1:a:0",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-shortest",
                            str(clip)], check=True, timeout=90)
            sha = hashlib.sha256(clip.read_bytes()).hexdigest()
            save(case / "packet.json", {"objective": question, "evidence": f"{a}: {x} {unit}. {b}: {y} {unit}.",
                                        "mp4_sha256": sha})
            rows.append({"id": opaque, "source_family": index, "seeded_change": unsafe, "sha256": sha})
            print(opaque, sha, flush=True)
    save(secure / "construction-key.json", rows)
    save(root / "label-template.json", {row["id"]: {"quality": None, "defect": None,
              "critical": None, "interval_seconds": None, "reason": ""} for row in sorted(rows, key=lambda r:r["id"])})


if __name__ == "__main__":
    main()
