"""Exercise validators not expressible in the frozen JSON Schema."""
import json
import sys

from pydantic import ValidationError
from storyboard_renderer.frame_api import Panel, Session
from video_renderer.api import Video


def main():
    raw = json.load(sys.stdin)
    try:
        video = Video.model_validate(raw)
        Session.model_validate(video.visual)
        for beat in video.beats:
            Panel.model_validate({**beat.panel, "key": beat.id,
                                  "parent_panel_id": "a" * 32 if beat.parent else None})
    except ValidationError as error:
        for entry in error.errors(include_url=False, include_input=False):
            print(f"{entry['loc']}: {entry['msg']}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
