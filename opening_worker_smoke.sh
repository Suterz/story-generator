#!/usr/bin/env bash
set -euo pipefail

# Intended to run inside one no-egress network namespace with loopback enabled.
# Do not use it to infer isolation from environment variables.
root="${1:?absolute three-repo root}"
store="${2:?isolated store}"
fresh="$HOME/ai/storyboard-rehearsal/fresh"
media="$HOME/ai/tools/media/bin"
mkdir -p "$store"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1

env PYTHONPATH="$root/frames/src" FRAME_STORE="$store/frames" \
    STORY_COMFY_URL=http://127.0.0.1:8188 \
    STORY_VISION_PYTHON="$fresh/venvs/storyboard-vision/bin/python" \
    STORY_VISION_MODEL="$fresh/models/vision/qwen3-vl-8b" \
    "$fresh/venvs/frames-renderer/bin/python" -B -m uvicorn storyboard_renderer.frame_api:app \
    --host 127.0.0.1 --port 8964 >"$store/frames.log" 2>&1 &
frames_pid=$!
env PYTHONPATH="$root/video/src" VIDEO_STORE="$store/video" VIDEO_FRAME_URL=http://127.0.0.1:8964 \
    VIDEO_SPEECH_ROOT="$fresh/speech" VIDEO_SPEECH_VENVS="$fresh/venvs" \
    STORY_FFMPEG="$media/ffmpeg" STORY_FFPROBE="$media/ffprobe" \
    "$fresh/venvs/video-renderer/bin/python" -B -m uvicorn video_renderer.api:app \
    --host 127.0.0.1 --port 8965 >"$store/video.log" 2>&1 &
video_pid=$!
trap 'kill "$frames_pid" "$video_pid" 2>/dev/null || true' EXIT

"$fresh/venvs/video-renderer/bin/python" -B - "$frames_pid" "$video_pid" <<'PY'
import json, os, socket, sys, time
from urllib.request import urlopen
from urllib.error import URLError

ours = os.readlink("/proc/self/ns/net")
for process in sys.argv[1:]:
    theirs = os.readlink(f"/proc/{process}/ns/net")
    if theirs != ours:
        raise SystemExit("worker shares different network policy")
    print("normal service process", process, theirs)
for host in ("api.openai.com", "1.1.1.1"):
    try:
        socket.create_connection((host, 443), timeout=3).close()
    except OSError as error:
        print("direct external connection denied:", host, type(error).__name__, error)
    else:
        raise SystemExit(f"unexpected network access: {host}")
for port in (8964, 8965):
    end = time.monotonic() + 15
    while True:
        try:
            with urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=2) as response:
                data = json.load(response)
            print("normal service API available:", port, data["info"]["title"])
            break
        except URLError:
            if time.monotonic() > end:
                raise
            time.sleep(.5)
PY
