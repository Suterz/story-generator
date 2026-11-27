#!/usr/bin/env python3
"""Bridge an isolated local worker to scoped publisher and Commons fetchers."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
from socketserver import BaseRequestHandler, UnixStreamServer
import sys
from tempfile import TemporaryDirectory

MAX = 18 * 1024 * 1024


def receive(stream):
    with stream.makefile("rb") as source:
        line = source.readline(MAX + 1)
    if len(line) > MAX:
        raise ValueError("broker message too large")
    return json.loads(line)


def send(stream, message):
    stream.sendall(json.dumps(message, ensure_ascii=False).encode() + b"\n")


class Handler(BaseRequestHandler):
    def handle(self):
        from daily_commons import pick
        from daily_fetch import discover, download, fetch

        self.request.settimeout(45)
        try:
            item = receive(self.request)
            mode, query = item["mode"], item["query"]
            if not isinstance(query, str) or not 1 <= len(query) <= 500:
                raise ValueError("invalid broker query")
            if mode == "document":
                result = fetch(query)
            elif mode == "discover":
                result = discover(query)
            elif mode == "commons":
                with TemporaryDirectory() as folder:
                    result = pick(query, Path(folder))
                    if "rights" in result:
                        asset = Path(folder) / result["rights"]["sha256"]
                        result["asset_bytes"] = base64.b64encode(asset.read_bytes()).decode()
            elif mode == "asset":
                result = download(query, limit=12*1024*1024, types={"image/jpeg", "image/png"},
                                  permitted=json.loads(os.environ.get("DAILY_IMAGE_HOSTS", "[]")))
                if "data" in result:
                    result["asset_bytes"] = base64.b64encode(result.pop("data")).decode()
            else:
                raise ValueError("unsupported broker operation")
        except (ValueError, KeyError, OSError) as error:
            result = {"error": str(error) or type(error).__name__}
        send(self.request, result)


def client(mode, query):
    with socket.socket(socket.AF_UNIX) as stream:
        stream.settimeout(45)
        stream.connect(os.environ["DAILY_BROKER_SOCKET"])
        send(stream, {"mode": mode, "query": query})
        return receive(stream)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "serve":
        path = Path(sys.argv[2])
        previous_mask = os.umask(0o077)
        try:
            with UnixStreamServer(str(path), Handler) as server:
                server.serve_forever()
        finally:
            os.umask(previous_mask)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("destination", nargs="?", type=Path)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--asset", action="store_true")
    args = parser.parse_args()
    if args.asset and not args.destination:
        parser.error("--asset requires an output path")
    mode = "asset" if args.asset else "commons" if args.destination else "discover" if args.discover else "document"
    result = client(mode, args.query)
    if args.asset and "asset_bytes" in result:
        args.destination.write_bytes(base64.b64decode(result.pop("asset_bytes"), validate=True))
    elif args.destination and "rights" in result:
        sha = result["rights"]["sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("broker returned invalid content hash")
        (args.destination / sha).write_bytes(base64.b64decode(result.pop("asset_bytes"), validate=True))
    print(json.dumps(result))
    if args.asset and "error" in result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
