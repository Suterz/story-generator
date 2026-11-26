"""Local brief-to-story CLI, with durable one-submit rendering."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import os
import re
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parent
HOME = Path.home()
SIGNATURES = {
    "market": "Original editorial cartoon, strong plum outlines, warm ivory paper, bright ochre fruit, teal leaves, rounded simple silhouettes.",
    "paper": "Standalone explanatory cartoon with warm cut-paper silhouettes, dark outlines, and minimal decoration.",
}


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def request(url, data=None, headers=None, timeout=30):
    body = None if data is None else json.dumps(data).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def brief_rule(brief):
    names = {"topic", "takeaway", "audience", "signature", "required_facts"}
    if not isinstance(brief, dict) or set(brief) != names:
        raise ValueError("brief requires topic, takeaway, audience, signature and required_facts")
    if not all(isinstance(brief[k], str) and brief[k].strip() for k in names - {"required_facts"}):
        raise ValueError("brief text fields must not be blank")
    facts = brief["required_facts"]
    if not isinstance(facts, list) or not facts or not all(isinstance(v, str) and v.strip() for v in facts):
        raise ValueError("required_facts must be a nonempty list of text")
    if brief["signature"] not in SIGNATURES:
        raise ValueError(f"unknown signature: {brief['signature']}")


def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.replace("’", "'").lower())


def validate(story):
    for name, data in (("Video", story), ("Session", story["visual"])):
        Draft202012Validator(read(ROOT / "schemas" / f"{name}.json")).validate(data)
    panel = Draft202012Validator(read(ROOT / "schemas/Panel.json"))
    script = {u["id"]: u for u in story["script"]}
    order = list(script)
    if len(script) != len(story["script"]):
        raise ValueError("duplicate script ID")
    if sum(len(words(u["text"])) for u in script.values()) > 75:
        raise ValueError("shorten narration to no more than 75 spoken tokens")
    if story["beats"][0]["cue"] != {"ms": 0}:
        raise ValueError("opening beat must start at ms=0")
    seen = {}
    previous = (-1, -1)
    for pos, b in enumerate(story["beats"]):
        key, parent, spec = b["id"], b.get("parent"), b["panel"]
        if key in seen or parent and parent not in seen:
            raise ValueError(f"{key}: duplicate beat or unavailable parent")
        if (spec["op"] == "new_scene") == bool(parent):
            raise ValueError(f"{key}: only a new scene has no parent")
        panel.validate({**spec, "key": key, "parent_panel_id": "a" * 32 if parent else None})
        cue = b["cue"]
        if pos:
            parts = words(cue["phrase"])
            utterance = words(script[cue["utterance_id"]]["text"])
            indexes = [i for i in range(len(utterance)) if utterance[i:i + len(parts)] == parts]
            n = cue.get("occurrence")
            if not parts or (n is None and len(indexes) != 1) or (n is not None and n > len(indexes)):
                raise ValueError(f"{key}: cue does not uniquely bind to the spoken words")
            place = (order.index(cue["utterance_id"]), indexes[(n or 1) - 1])
            if place <= previous:
                raise ValueError(f"{key}: cue must follow the preceding panel")
            previous = place
        seen[key] = b
    rule = story.get("instructional")
    if rule:
        question = script[rule["question_utterance"]]
        if question.get("pause_after_ms", 0) < rule["minimum_ms"]:
            raise ValueError("prediction pause shorter than authored minimum")
        answer = seen[rule["answer_beat"]]
        if order.index(answer["cue"]["utterance_id"]) <= order.index(question["id"]):
            raise ValueError("answer beat is not after the question")
    return story


@contextmanager
def writer(args, model, log):
    with args.lease.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        cmd = [str(args.runtime), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
               "-c", "8192", "-ngl", "99", "-np", "1", "--jinja"]
        with log.open("w") as stream:
            proc = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT)
            try:
                end = time.monotonic() + 120
                while time.monotonic() < end:
                    if proc.poll() is not None:
                        raise RuntimeError(f"writer startup failed: {log}")
                    try:
                        request(base + "/health", timeout=2)
                        break
                    except (URLError, TimeoutError):
                        time.sleep(.3)
                else:
                    raise TimeoutError("writer readiness timeout")
                yield base
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def write(args):
    out = args.out
    if (out / "story.json").exists():
        return validate(read(out / "story.json"))
    brief = read(args.input)
    brief_rule(brief)
    skill = (ROOT / "skills/lesson-writer/v1/SKILL.md").read_text()
    config = read(ROOT / "models.json")[args.model]
    model = args.models / config["file"]
    with model.open("rb") as asset:
        actual = hashlib.file_digest(asset, "sha256").hexdigest()
    if actual != config["sha256"]:
        raise ValueError("writer checkpoint hash mismatch")
    meta = {"brief": brief, "model": config, "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
            "seed": 437, "temperature": .6, "top_p": .95, "max_tokens": 3300, "voice": args.voice}
    if (out / "writer.json").exists() and read(out / "writer.json") != meta:
        raise ValueError("cannot resume with a changed brief or writer configuration")
    save(out / "writer.json", meta)
    errors = []
    with writer(args, model, out / "llama.log") as endpoint:
        for attempt in range(2):
            artifact = out / f"writer-attempt-{attempt}.json"
            if artifact.exists():
                result = read(artifact)
            else:
                prompt = skill + "\nReturn one JSON object with title, visual, script, beats, and instructional.\n"
                prompt += "Brief:\n" + json.dumps(brief, ensure_ascii=False)
                prompt += "\nUse this exact visual signature: " + SIGNATURES[brief["signature"]]
                if errors:
                    prompt += "\nCorrect this validation failure without changing any required fact: " + errors[-1]
                t = time.monotonic()
                data = {"messages": [{"role": "user", "content": prompt}],
                        "seed": meta["seed"], "temperature": meta["temperature"], "top_p": meta["top_p"],
                        "max_tokens": meta["max_tokens"], "response_format": {"type": "json_object"}}
                result = json.loads(request(endpoint + "/v1/chat/completions", data, timeout=240))
                save(artifact, {"seconds": time.monotonic() - t, "response": result})
                result = read(artifact)
            try:
                story = json.loads(result["response"]["choices"][0]["message"]["content"])
                story["voice_profile"] = args.voice
                story["visual"]["visual_signature"] = SIGNATURES[brief["signature"]]
                validate(story)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(str(exc))
            except Exception as exc:
                from jsonschema import ValidationError
                if not isinstance(exc, ValidationError):
                    raise
                errors.append(f"{list(exc.path)}: {exc.message}")
            else:
                save(out / "story.json", story)
                return story
    save(out / "writer-refusal.json", {"diagnostics": errors})
    raise ValueError("writer did not produce a supported story: " + errors[-1])


def render(args, story):
    out = args.out
    if (out / "outcome.json").exists():
        return read(out / "outcome.json")
    digest = hashlib.sha256(json.dumps(story, sort_keys=True).encode()).hexdigest()
    key = "storygen-" + hashlib.sha256(f"{out.resolve()}:{digest}".encode()).hexdigest()
    receipt = out / "submission.json"
    base = args.video_url.rstrip("/")
    info = {"key": key, "digest": digest, "endpoint": base}
    if receipt.exists():
        if read(receipt) != info:
            raise ValueError("cannot resume with a different story or endpoint")
        status = json.loads(request(f"{base}/v2/submissions/{key}"))
    else:
        save(receipt, info)
        status = json.loads(request(base + "/v2/renders", story, {"Idempotency-Key": key}))
    deadline = time.monotonic() + 1800
    while status["state"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(2)
        status = json.loads(request(base + status["status_url"]))
    if status["state"] in {"queued", "running"}:
        raise TimeoutError("job still active; resume with the same output directory")
    if status["state"] == "succeeded":
        video = request(base + status["video_url"])
        (out / "video.partial.mp4").write_bytes(video)
        (out / "video.partial.mp4").replace(out / "video.mp4")
        save(out / "manifest.json", json.loads(request(base + status["status_url"] + "/manifest")))
        status["download_sha256"] = hashlib.sha256(video).hexdigest()
    save(out / "outcome.json", status)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("write", "render", "run"))
    p.add_argument("input", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--video-url", default="http://127.0.0.1:8893")
    p.add_argument("--model", choices=("qwen", "mistral", "deepseek"), default="qwen")
    p.add_argument("--models", type=Path, default=HOME / "ai/storyboard-rehearsal/writer/models")
    p.add_argument("--runtime", type=Path, default=HOME / "ai/storyboard-rehearsal/writer/runtime/build/bin/llama-server")
    p.add_argument("--lease", type=Path, default=HOME / "ai/storyboard-build/v2/gpu.lock")
    p.add_argument("--voice", choices=("heart", "ryan"), default="ryan")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == "render":
            story = validate(read(args.input))
        else:
            story = write(args)
        if args.command != "write":
            print(json.dumps(render(args, story), indent=2))


if __name__ == "__main__":
    main()
