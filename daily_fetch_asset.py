#!/usr/bin/env python3
"""Fetch one approved original; the frame service verifies its expected hash."""
import json
import os
from pathlib import Path
import sys

from daily_fetch import download


def main():
    url, output = sys.argv[1:]
    result = download(url, limit=12*1024*1024, types={"image/jpeg", "image/png"},
                      permitted=json.loads(os.environ.get("DAILY_IMAGE_HOSTS", "[]")))
    if "error" in result:
        print(json.dumps(result), file=sys.stderr)
        return 1
    Path(output).write_bytes(result["data"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
