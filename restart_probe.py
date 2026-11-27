"""Restart an isolated episode worker after its first durable speech checkpoint."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import URLError

from storygen import read, request, save


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("request", type=Path)
    p.add_argument("video_repo", type=Path)
    p.add_argument("tool_root", type=Path)
    p.add_argument("store", type=Path)
    a = p.parse_args()
    base = "http://127.0.0.1:8937"
    b = a.tool_root
    env = {**os.environ, "VIDEO_PORT":"8937", "VIDEO_FRAME_URL":"http://127.0.0.1:8927",
           "VIDEO_STORE":str(a.store), "HF_HOME":str(b/"hf-cache"),
           "VIDEO_PYTHON":str(b/"venvs/video-renderer/bin/python"), "VIDEO_SPEECH_ROOT":str(b/"speech"),
           "VIDEO_SPEECH_VENVS":str(b/"venvs"), "STORY_FFMPEG":str(b/"media/bin/ffmpeg"),
           "STORY_FFPROBE":str(b/"media/bin/ffprobe")}
    a.store.mkdir(parents=True, exist_ok=False)
    key = "long-form-diagnostic-restart-01"
    receipt = a.store / "probe.json"
    with (a.store / "server.log").open("w") as log:
        def start():
            child = subprocess.Popen(["./bin/start-video-renderer"], cwd=a.video_repo,
                                     env=env, stdout=log, stderr=subprocess.STDOUT)
            for _ in range(45):
                try:
                    request(base + "/ready", timeout=2)
                    return child
                except URLError:
                    if child.poll() is not None:
                        raise RuntimeError("isolated renderer did not start")
                    time.sleep(1)
            child.terminate()
            raise RuntimeError("isolated renderer never became ready")
        child = start()
        try:
            first = json.loads(request(base + "/v2/episodes", read(a.request), {"Idempotency-Key":key}))
            save(receipt, {"initial":first})
            job = a.store / first["id"]
            checkpoint = job / "group-0.json"
            end = time.monotonic()+150
            while not checkpoint.is_file() and time.monotonic() < end:
                time.sleep(1)
            digest = hashlib.sha256((job / "group-0.pcm.wav").read_bytes()).hexdigest()
            before = read(job/"status.json")
            if before["state"] != "running":
                raise ValueError("diagnostic did not stop during active work")
            child.terminate()
            child.wait(timeout=25)
            child = start()
            after = json.loads(request(base + "/v2/submissions/" + key))
            assert after["id"] == first["id"]
            end = time.monotonic()+1000
            while after["state"] in ("queued","running") and time.monotonic() < end:
                time.sleep(3)
                after = json.loads(request(base + after["status_url"]))
            assert hashlib.sha256((job / "group-0.pcm.wav").read_bytes()).hexdigest() == digest
            save(receipt, {"initial":first, "before_restart":before, "terminal":after,
                           "preserved_group_0_pcm_sha256":digest})
        finally:
            child.terminate()
            child.wait(timeout=25)


if __name__ == "__main__":
    main()
