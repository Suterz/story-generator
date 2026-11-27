#!/usr/bin/env bash
set -euo pipefail

repos="$(realpath "${1:?three-repository root}")"
store="$(realpath -m "${2:?new run directory}")"
brief="$(realpath "${3:?development brief}")"
freeze="$(realpath "${4:?development configuration receipt}")"
image=ubuntu@sha256:562111b88caa79c71391c0c4d3c2114a7d5c35915c20561fd893cb1e07929e6b
lease="$HOME/ai/storyboard-build/v2/gpu.lock"
mkdir "$store"
chmod 700 "$store"
socket="$store/broker.sock"
finish() {
    local code=$?
    if [[ -n "${broker:-}" ]]; then kill "$broker" 2>/dev/null || true; fi
    python3 -B - "$store" "$code" <<'PY'
import hashlib, json, sys
from pathlib import Path

root = Path(sys.argv[1])
terminal = root / "opening/terminal-outcome.json"
if terminal.is_file():
    data = terminal.read_bytes()
    review = json.loads(data)
    outcome = {"status": review["status"], "exit": int(sys.argv[2]),
               "terminal_sha256": hashlib.sha256(data).hexdigest()}
else:
    outcome = {"status": "withheld", "code": "isolated_stack_incomplete", "exit": int(sys.argv[2]),
               "detail": "Worker startup, broker, or opening did not reach a terminal receipt; see control.log."}
tmp = root / "operating-outcome.partial"
tmp.write_text(json.dumps(outcome, indent=2) + "\n")
tmp.replace(root / "operating-outcome.json")
PY
}
trap finish EXIT
sed s/libGLX_nvidia/libEGL_nvidia/ /usr/share/vulkan/icd.d/nvidia_icd.json >"$store/nvidia-egl.json"

mapfile -t drm < <(for device in /sys/class/drm/card* /sys/class/drm/renderD*; do
    if [[ -f "$device/device/vendor" && "$(cat "$device/device/vendor")" == 0x10de ]]; then
        echo "--device=/dev/dri/${device##*/}"
    fi
done)
[[ "${#drm[@]}" -gt 0 ]]

DAILY_PUBLISHERS='{"www.eia.gov":"U.S. Energy Information Administration"}' \
DAILY_IMAGE_HOSTS='["eol.jsc.nasa.gov"]' \
DAILY_HTTP_AGENT='Storyboard Opening Qualification development' \
python3 -B "$repos/story/opening_broker.py" serve "$socket" >"$store/broker.log" 2>&1 &
broker=$!
for (( i=0; i<20; i++ )); do
    [[ ! -S "$socket" ]] || break
    sleep .2
done
[[ -S "$socket" ]]

docker run --rm --network none --user "$(id -u):$(id -g)" \
    --group-add "$(getent group render | cut -d: -f3)" --group-add "$(getent group video | cut -d: -f3)" \
    --device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm --device /dev/nvidia-modeset \
    "${drm[@]}" \
    -v /usr/bin:/usr/bin:ro -v /usr/lib:/usr/lib:ro -v /usr/libexec:/usr/libexec:ro \
    -v /usr/include:/usr/include:ro -v /usr/share/fonts:/usr/share/fonts:ro \
    -v /usr/share/vulkan:/usr/share/vulkan:ro -v "$HOME:$HOME:ro" -v "$store:$store" -v "$lease:$lease" \
    -e HOME="$HOME" -e DAILY_FREEZE="$freeze" -e DAILY_BROKER_SOCKET="$socket" \
    -e OPENING_WRITER="${OPENING_WRITER:-bound-options-v12}" \
    -e OPENING_REPEAT="${OPENING_REPEAT:-1}" \
    -e VK_DRIVER_FILES="$store/nvidia-egl.json" -e LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu \
    -e DAILY_SMOKE_TEXT_URL=https://www.eia.gov/energyexplained/electricity/electricity-in-the-us.php \
    -e DAILY_SMOKE_IMAGE_URL=https://eol.jsc.nasa.gov/DatabaseImages/ESC/large/ISS064/ISS064-E-29444.JPG \
    "$image" /bin/bash "$repos/story/opening_isolated_stack.sh" "$repos" "$store" "$brief" \
    2>&1 | tee "$store/control.log"
