#!/usr/bin/env bash
set -euo pipefail

# Run inside a worker-only network namespace with a private store and a
# shared GPU lease. The retrieval broker resides outside this namespace.
repos="${1:?three-repository root}"
store="${2:?writable private run store}"
brief="${3:?daily/2 development brief}"
fresh="$HOME/ai/storyboard-rehearsal/fresh"
fish="$HOME/ai/autonomous-daily/next/fish-comfy"
writer="$HOME/ai/storyboard-rehearsal/writer"
media="$HOME/ai/tools/media/bin"
pids=()
trap 'if ((${#pids[@]})); then kill "${pids[@]}" 2>/dev/null || true; fi' EXIT
mkdir -p "$store"/{fish-output,fish-input,fish-temp,fish-user,flux-output,flux-input,flux-temp,flux-user}
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export DAILY_FRAMES_REPO="$repos/frames" DAILY_VIDEO_REPO="$repos/video"
export DAILY_SOURCE_CACHE="$store/source-cache" DAILY_ASSET_CACHE="$store/asset-cache"
export HF_HOME="$store/hf-home" XDG_CACHE_HOME="$store/cache"
export TRITON_CACHE_DIR="$store/cache/triton" TORCHINDUCTOR_CACHE_DIR="$store/cache/inductor"
export CUDA_CACHE_PATH="$store/cache/cuda"
export STORY_VISION_MODEL="$fresh/models/vision/qwen3-vl-8b"
export STORY_FFMPEG="$media/ffmpeg" STORY_FFPROBE="$media/ffprobe"
export STORY_COMFY_URL=http://127.0.0.1:8188 VIDEO_DRAMA3_PORT=8960
export VIDEO_DRAMA3_OUTPUT="$store/fish-output"
export VIDEO_SPEECH_ROOT="$fresh/speech" VIDEO_SPEECH_VENVS="$fresh/venvs"
export DAILY_FETCH_PROGRAM="$repos/story/opening_broker.py"
export DAILY_IMAGE_DISCOVERY="$repos/story/opening_broker.py"
printf '#include <Python.h>\nint compiler_check(void) { return PY_MAJOR_VERSION; }\n' \
    | /usr/bin/gcc -x c -shared -fPIC -I /usr/include/python3.12 -o "$store/compiler-check.so" -

launch() {
    local name="$1"
    shift
    "$@" >"$store/$name.log" 2>&1 &
    pids+=("$!")
    printf '%s %s %s\n' "$name" "$!" "$(readlink "/proc/$!/ns/net")"
}

launch fish "$fresh/venvs/comfy-storyboard/bin/python" -B "$fish/main.py" \
    --listen 127.0.0.1 --port 8960 --base-directory "$fish" \
    --output-directory "$store/fish-output" --input-directory "$store/fish-input" \
    --temp-directory "$store/fish-temp" --user-directory "$store/fish-user" --disable-api-nodes
launch flux "$fresh/venvs/comfy-storyboard/bin/python" -B "$fresh/ComfyUI/main.py" \
    --listen 127.0.0.1 --port 8188 --base-directory "$fresh/ComfyUI" \
    --output-directory "$store/flux-output" --input-directory "$store/flux-input" \
    --temp-directory "$store/flux-temp" --user-directory "$store/flux-user" --disable-all-custom-nodes
launch frames env PYTHONPATH="$repos/frames/src" FRAME_STORE="$store/frames" \
    STORY_VISION_PYTHON="$fresh/venvs/storyboard-vision/bin/python" \
    "$fresh/venvs/frames-renderer/bin/python" -B -m uvicorn storyboard_renderer.frame_api:app \
    --host 127.0.0.1 --port 8964
launch video env PYTHONPATH="$repos/video/src" VIDEO_STORE="$store/video" VIDEO_FRAME_URL=http://127.0.0.1:8964 \
    "$fresh/venvs/video-renderer/bin/python" -B -m uvicorn video_renderer.api:app --host 127.0.0.1 --port 8965

python3 -B - "${pids[@]}" <<'PY'
import os, socket, sys, time
from urllib.request import urlopen
from urllib.error import URLError

namespace = os.readlink("/proc/self/ns/net")
assert all(os.readlink(f"/proc/{pid}/ns/net") == namespace for pid in sys.argv[1:])
assert not any(value for key, value in os.environ.items() if "OPENAI" in key.upper())
for destination in ("api.openai.com", "1.1.1.1"):
    try:
        with socket.create_connection((destination, 443), timeout=3):
            raise RuntimeError(f"unexpected direct egress to {destination}")
    except OSError as error:
        print("direct egress failed", destination, repr(error), flush=True)
for endpoint in ("http://127.0.0.1:8960/object_info/Drama3LoadVoice", "http://127.0.0.1:8965/ready"):
    deadline = time.monotonic()+100
    while True:
        try:
            with urlopen(endpoint, timeout=3):
                print("available", endpoint, flush=True)
                break
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
PY

cd "$repos/story"
if [[ -n "${DAILY_SMOKE_TEXT_URL:-}" && -n "${DAILY_SMOKE_IMAGE_URL:-}" ]]; then
    "$DAILY_FETCH_PROGRAM" "$DAILY_SMOKE_TEXT_URL" >"$store/broker-text.json"
    "$DAILY_FETCH_PROGRAM" --asset "$DAILY_SMOKE_IMAGE_URL" "$store/broker-image.jpg" >"$store/broker-image.json"
    python3 -B - "$store/broker-text.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    packet = json.load(stream)
if "error" in packet or not packet.get("sha256"):
    raise SystemExit(f"broker text failed: {packet.get('error')}")
print("broker text allowed", packet["sha256"], flush=True)
PY
    sha256sum "$store/broker-image.jpg"
fi
mkdir -p "$TRITON_CACHE_DIR" "$TORCHINDUCTOR_CACHE_DIR" "$CUDA_CACHE_PATH"
exec_status=0
"$writer/venv/bin/python" -B storygen.py run "$brief" --out "$store/opening" \
    --model mistral-small --voice drama3-A --opening-preview "${OPENING_WRITER:-complete-pack-v13}" \
    --opening-reviewer focus-is-relation-v5 --video-url http://127.0.0.1:8965 \
    --validator-python "$fresh/venvs/video-renderer/bin/python" --frames-repo "$repos/frames" --video-repo "$repos/video" \
    || exec_status=$?
exit "$exec_status"
