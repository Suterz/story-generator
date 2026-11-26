"""Prepare assisted options and put them behind each slot's original receipt."""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave

from morning_art import DESIGNS, PAPER, stage_art
from storygen import ROOT, read, save


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def capture_frames(source, manifest, dest, ffmpeg):
    end = manifest["verification"]["expected_video_frames"] - 1
    cuts = [b["frame"] for b in manifest["beats"]]
    frames = sorted({0, end, *cuts, *(max(0, c - 1) for c in cuts)})
    graph = "+".join(f"eq(n\\,{f})" for f in frames)
    subprocess.run([str(ffmpeg), "-v", "error", "-y", "-i", str(source), "-an", "-vf",
                    f"select={graph},scale=360:640,tile={len(frames)}x1",
                    "-frames:v", "1", str(dest)], check=True, timeout=80)
    return frames


def stage(out, toolroot, frames_repo, video_repo, frames_url):
    """No speech is intended here; assemble accepted frames with an original bell."""
    f = out / "narration.wav"
    if not f.exists():
        rate = 48000
        recording = array("h", [0]) * (rate * 9)
        for i in range(rate * 2):
            t = i / rate
            ramp = min(1, t / .018)
            ringing = (math.sin(2*math.pi*660*t)+.28*math.sin(2*math.pi*997*t)) * math.exp(-2.8*t)
            recording[rate*4+i] = round(2500*ramp*ringing)
        with wave.open(str(f), "wb") as w:
            w.setparams((1, 2, rate, len(recording), "NONE", "not compressed"))
            w.writeframes(recording.tobytes())
    program = """
import sys,time,json
from pathlib import Path
import httpx
from morning_art import PAPER,stage_art
from video_renderer.media import encode
out=Path(sys.argv[1]); base=sys.argv[2]; pictures=[]
with httpx.Client(base_url=base,timeout=30) as client:
    receipt=out/'frame-session.json'
    if receipt.exists(): session=json.loads(receipt.read_text())
    else:
        r=client.post('/v2/sessions',json={'story_context':'An empty stage before a performance','visual_signature':PAPER,'graphic_theme':'paper'})
        r.raise_for_status();session=r.json();receipt.write_text(json.dumps(session))
    sid=session['session_id']
    parent=None
    for i in range(2):
        request=dict(key=f'stage{i}',op='new_scene' if i==0 else 'overlay_only',scene_id='stage',
            objective='A still empty stage; only its light changes',instruction='Closed curtain and a low light',
            overlays=stage_art(bool(i)),retry_budget=0)
        if i:request['parent_panel_id']=parent
        else:request['paper_scene']=True
        r=client.post(f'/v2/sessions/{sid}/panels',json=request);r.raise_for_status(); a=r.json()
        while a['state'] in ('queued','running'):
            time.sleep(1);r=client.get(a['status_url']);r.raise_for_status();a=r.json()
        if a['state']!='accepted':raise ValueError(a)
        parent=a['panel_id']; pic=out/f'frame{i}.png'
        r=client.get(a['artifacts']['composed.png']); r.raise_for_status();pic.write_bytes(r.content)
        pictures.append(pic)
        (out/f'frame{i}-status.json').write_text(json.dumps(a,indent=2))
v=encode(pictures,[(0,144,0),(144,270,1)],(1080,1920),30,270,out/'narration.wav',out/'video.mp4')
(out/'manifest.json').write_text(json.dumps({'verification':v,'beats':[{'frame':0},{'frame':144}],
    'audio':'Original synthesized bell at 4.00 seconds; no speech; light rises at 4.80 seconds'},indent=2))
"""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (ROOT, frames_repo / "src", video_repo / "src"))),
           "STORY_FFMPEG": str(toolroot / "media/bin/ffmpeg"), "STORY_FFPROBE": str(toolroot / "media/bin/ffprobe")}
    subprocess.run([str(toolroot / "venvs/video-renderer/bin/python"), "-B", "-c", program, str(out), frames_url],
                   env=env, check=True, timeout=1000)
    save(out / "outcome.json", {"state": "succeeded", "download_sha256": sha(out / "video.mp4")})


def record_pause(out, toolroot, video_repo, url, request, *, submit=True):
    """Repeat exactly the same PCM; add silence only before 'slowly'."""
    text = "The door opened slowly."
    speech = toolroot / "speech"
    ffmpeg = toolroot / "media/bin/ffmpeg"
    worker = video_repo / "src/video_renderer/speech_worker.py"
    env = {**os.environ, "STORY_FFMPEG": str(ffmpeg), "HF_HUB_OFFLINE": "1",
           "TRANSFORMERS_OFFLINE": "1", "PATH": f"{speech}/espeak/usr/bin:{os.environ['PATH']}",
           "PHONEMIZER_ESPEAK_LIBRARY": "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"}
    raw, canonical, result = (out / x for x in ("raw.wav", "single.wav", "exact-repeat.wav"))
    if not result.exists():
        for name, wav in (("heart", raw), ("align", canonical)):
            output = subprocess.check_output(
                [str(toolroot / f"venvs/v2-{name}/bin/python"), "-B", str(worker), name, str(speech), str(wav)],
                input=json.dumps({"text": text}).encode(), env=env, timeout=300)
            if name == "heart":
                subprocess.run([str(ffmpeg), "-v", "error", "-y", "-i", str(raw),
                                "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(canonical)], check=True)
        spans = json.loads(output.splitlines()[-1])
        slowly = next(s for s in spans if s["word"].casefold().strip(".") == "slowly")
        # Split between words rather than through the s onset. No passage
        # is synthesized twice: both lines are copied from the same WAV.
        split = round((slowly["start"] - .015) * 48000) * 2
        with wave.open(str(canonical), "rb") as w:
            pcm = w.readframes(w.getnframes())
        with wave.open(str(result), "wb") as w:
            w.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            w.writeframes(pcm + b"\0" * 96000 + pcm[:split] + b"\0" * 96000 + pcm[split:])
        save(out / "pause-proof.json", {"repeated_pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                                       "second_pass_inserted_silence_ms": 1000, "split_sample": split // 2})
    if submit:
        subprocess.run([str(toolroot / "venvs/video-renderer/bin/python"), "-B",
                        str(video_repo / "benchmark/replay_recording.py"), str(request), str(result),
                        "--out", str(out), "--url", url], check=True, timeout=1200)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("root", "toolroot", "frames", "video"):
        p.add_argument("--" + arg, type=Path, required=True)
    p.add_argument("--video-url", required=True)
    p.add_argument("--frames-url", required=True)
    p.add_argument("--slot", action="append")
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--decode-first", action="store_true")
    a = p.parse_args()
    job, first = a.root / "assisted", a.root / "first"
    ffmpeg = a.toolroot / "media/bin/ffmpeg"
    job.mkdir(exist_ok=True)
    for slot in a.slot or [f"{i:02}" for i in range(1, 21)]:
        initial = first / slot
        if a.decode_first:
            if ((initial / "outcome.json").is_file() and read(initial / "outcome.json")["state"] == "succeeded"
                    and not (initial / "phone.png").exists()):
                frames = capture_frames(initial / "video.mp4", read(initial / "manifest.json"), initial / "phone.png", ffmpeg)
                save(initial / "gallery.json", {"sample_frames": frames, "sha256": sha(initial / "video.mp4")})
            continue
        folder = job / slot
        folder.mkdir(exist_ok=True)
        control = {"01": "contract-control/heart", "02": "empathy-authored-control"}.get(slot)
        if slot in DESIGNS:
            request = folder / "story.json"
            if not request.exists():
                save(request, DESIGNS[slot]())
        if a.prepare:
            if slot == "12":
                record_pause(folder, a.toolroot, a.video, a.video_url, request, submit=False)
            continue
        if not any((initial / name).exists() for name in ("outcome.json", "result.json", "writer-refusal.json", "cli.json")):
            continue
        if (initial / "outcome.json").exists() and read(initial / "outcome.json")["state"] == "succeeded":
            if not (initial / "incorrect-accepted.json").exists():
                continue  # only use an alternative after reviewing the delivered first clip
        if (folder / "phone.png").exists():
            continue
        if control:
            original = a.root.parent / "story-communication" / control
            for name in ("story.json", "video.mp4", "manifest.json", "outcome.json"):
                if (original / name).exists():
                    shutil.copyfile(original / name, folder / name)
        elif slot == "19":
            try:
                stage(folder, a.toolroot, a.frames, a.video, a.frames_url)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                save(folder / "operational.json", {"reason": str(error)})
                continue
        elif slot == "12":
            try:
                record_pause(folder, a.toolroot, a.video, a.video_url, request)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                save(folder / "operational.json", {"reason": str(error)})
                continue
        else:
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "storygen.py"), "render", str(request),
                 "--out", str(folder), "--video-url", a.video_url,
                 "--validator-python", str(a.toolroot / "venvs/video-renderer/bin/python"),
                 "--frames-repo", str(a.frames), "--video-repo", str(a.video)],
                capture_output=True, text=True)
            (folder / "render.log").write_text(result.stdout + result.stderr)
            if result.returncode:
                print(slot, "assisted error", result.returncode, flush=True)
                continue
        if (folder / "outcome.json").exists() and read(folder / "outcome.json")["state"] == "succeeded":
            frames = capture_frames(folder / "video.mp4", read(folder / "manifest.json"), folder / "phone.png", ffmpeg)
            save(folder / "gallery.json", {"sample_frames": frames, "sha256": sha(folder / "video.mp4"),
                                            "assistance": "agent-assisted", "source": control or "authored storyboard"})
            print(slot, "candidate ready for review", flush=True)
        else:
            print(slot, "assisted still withheld", flush=True)


if __name__ == "__main__":
    main()
