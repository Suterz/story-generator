"""Join a fixed opening to either body; verify the delivered decoded prefix."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def run(ffmpeg, args, **kwargs):
    return subprocess.run([str(ffmpeg), "-v", "error", "-xerror", *args],
                          check=True, timeout=300, **kwargs)


def frames(ffmpeg, source, length=None):
    args = ["-i", str(source), "-an"]
    if length:
        args.extend(["-frames:v", str(length)])
    args += ["-f", "framehash", "-"]
    return [row.rsplit(",", 1)[-1].strip() for row in
            run(ffmpeg, args, capture_output=True, text=True).stdout.splitlines() if not row.startswith("#")]


def build(opening, body, offset, output, ffmpeg):
    with TemporaryDirectory(prefix="matched-body-") as directory:
        temp = Path(directory)
        # Lossless intermediary makes the separately encoded prefix testable.
        for name, path, at in (("opening", opening, 0), ("body", body, offset)):
            run(ffmpeg, ["-ss", str(at), "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
                         "-vf", "scale=360:640,fps=30,setsar=1", "-c:v", "ffv1", "-pix_fmt", "yuv420p",
                         "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(temp / f"{name}.mkv")])
        parts = temp / "parts.txt"
        parts.write_text("file 'opening.mkv'\nfile 'body.mkv'\n")
        run(ffmpeg, ["-f", "concat", "-safe", "1", "-i", str(parts), "-c:v", "libx264",
                     "-crf", "0", "-c:a", "alac", str(output)])
        prefix = frames(ffmpeg, temp / "opening.mkv")
        decoded = frames(ffmpeg, output, len(prefix))
        if prefix != decoded:
            raise ValueError("matched assembly changed decoded opening video")
        audio = ["-map", "0:a:0", "-f", "s16le", "-"]
        original = run(ffmpeg, ["-i", str(temp / "opening.mkv"), *audio], capture_output=True).stdout
        final = run(ffmpeg, ["-i", str(output), "-af", f"atrim=end_sample={len(original)//2}", *audio],
                    capture_output=True).stdout
        if final != original:
            raise ValueError("matched assembly changed decoded opening audio")
        return {"opening_frames": len(prefix), "opening_pcm_sha256": hashlib.sha256(original).hexdigest(),
                "opening_decoded_video_sha256": hashlib.sha256("".join(prefix).encode()).hexdigest(),
                "body_offset_seconds": offset, "mp4_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("opening", "body", "output"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--body-offset", required=True, type=float)
    parser.add_argument("--ffmpeg", type=Path, default=Path.home() / "ai/tools/media/bin/ffmpeg")
    args = parser.parse_args()
    outcome = build(args.opening, args.body, args.body_offset, args.output, args.ffmpeg)
    args.output.with_suffix(".json").write_text(json.dumps(outcome, indent=2) + "\n")
