"""Exercise validators not expressible in the frozen JSON Schema."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PIL import Image
from pydantic import ValidationError
from storyboard_renderer.compose import compose
from storyboard_renderer.frame_api import Panel, Session
from storyboard_renderer.grounding import NeedsReview
from video_renderer.api import Video


def check_label_spacing(panel, session, temp):
    """Use real renderer font boxes for labels with authored coordinates."""
    size = session.canvas
    base = temp / "empty.png"
    Image.new("RGB", size, "white").save(base)
    found = []
    for label in panel.overlays:
        if label.type not in ("text", "label") or not isinstance(label.at, list):
            continue
        alpha = temp / "label-alpha.png"
        compose(base, [label], "", session.values, {}, size, temp / "label.png",
                alpha, theme=session.graphic_theme)
        with Image.open(alpha) as im:
            box = im.getchannel("A").getbbox()
        if not box:
            continue
        for other, previous in found:
            intersect = (min(box[2], previous[2]) - max(box[0], previous[0]),
                         min(box[3], previous[3]) - max(box[1], previous[1]))
            if min(intersect) >= 4:
                raise ValueError(f"{panel.key}: labels {other!r} and {label.text!r} overlap at phone size; separate them")
        found.append((label.text, box))


def main():
    raw = json.load(sys.stdin)
    try:
        video = Video.model_validate(raw)
        session = Session.model_validate(video.visual)
        with TemporaryDirectory(prefix="storygen-preflight-") as folder:
            for beat in video.beats:
                panel = Panel.model_validate({**beat.panel, "key": beat.id,
                                              "parent_panel_id": "a" * 32 if beat.parent else None})
                check_label_spacing(panel, session, Path(folder))
    except ValidationError as error:
        for entry in error.errors(include_url=False, include_input=False):
            print(f"{entry['loc']}: {entry['msg']}")
        return 2
    except (ValueError, NeedsReview) as error:
        print(error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
