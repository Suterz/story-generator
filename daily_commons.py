#!/usr/bin/env python3
"""Discover licensed own-work photos; output original bytes plus an item receipt."""
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, urlsplit

from daily_fetch import download


COMMONS = "commons.wikimedia.org"
UPLOAD = "upload.wikimedia.org"
API = "https://" + COMMONS + "/w/api.php?"
LICENSES = {
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "https://creativecommons.org/licenses/by/3.0/": "CC BY 3.0",
}


def api(params):
    response = download(API + urlencode({"action": "query", "format": "json", "formatversion": 2, **params}),
                        limit=512*1024, types={"application/json"}, permitted={COMMONS})
    if "error" in response:
        raise ValueError(response["error"])
    return json.loads(response["data"])["query"]["pages"], response["requests"]


def field(metadata, key):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", metadata.get(key, {}).get("value", ""))).split())


def pick(query, directory):
    if len(query) > 140 or not query.strip():
        return {"error": "expected a short public image search phrase"}
    index, requests = api({"generator": "search", "gsrsearch": query + " filetype:bitmap",
                           "gsrnamespace": 6, "gsrlimit": 3})
    candidates = []
    for page in sorted(index, key=lambda row: row.get("index", 0)):
        rows, count = api({"pageids": page["pageid"], "prop": "imageinfo|revisions", "rvprop": "ids",
                          "iiprop": "url|mime|size|extmetadata"})
        requests += count
        entry = rows[0]
        image = entry["imageinfo"][0]
        metadata = image["extmetadata"]
        license_url = field(metadata, "LicenseUrl").replace("http://", "https://", 1).rstrip("/") + "/"
        maker = field(metadata, "Artist")
        original = image["url"]
        title = entry["title"]
        candidates.append({"title": title, "page": image["descriptionurl"], "status": "rights_unconfirmed"})
        if (field(metadata, "Credit").casefold() != "own work" or not maker
                or field(metadata, "Restrictions") or len(maker) > 300 or license_url not in LICENSES
                or entry.get("imagerepository") != "local" or urlsplit(original).hostname != UPLOAD
                or urlsplit(image["descriptionurl"]).hostname != COMMONS):
            continue
        if (image["mime"] not in {"image/jpeg", "image/png"} or min(image["width"], image["height"]) < 480
                or image["width"] * image["height"] > 30_000_000 or image["size"] > 12*1024*1024):
            candidates[-1]["status"] = "size_or_format"
            continue
        response = download(original, limit=12*1024*1024, types={"image/jpeg", "image/png"}, permitted={UPLOAD})
        requests += response.get("requests", 0)
        if "error" in response:
            candidates[-1]["status"] = response["error"]
            continue
        raw = response["data"]
        hash_ = hashlib.sha256(raw).hexdigest()
        (directory / hash_).write_bytes(raw)
        candidates[-1]["status"] = "acquired"
        revision = entry["revisions"][0]["revid"]
        return {"requests": requests, "candidates": candidates, "rights": {
            "page": image["descriptionurl"], "file": original, "title": title, "creator": maker,
            "credit": f"{title.removeprefix('File:')} — {maker} ({LICENSES[license_url]}); resized.",
            "basis": LICENSES[license_url], "rights_page": license_url, "checked":
                datetime.now(timezone.utc).date().isoformat(),
            "original_page_revision": revision, "sha256": hash_, "commercial_editorial": True, "resize": True}}
    return {"error": "no original with confirmed commercial editorial rights", "requests": requests,
            "candidates": candidates}


if __name__ == "__main__":
    try:
        print(json.dumps(pick(sys.argv[1], Path(sys.argv[2]))))
    except (KeyError, ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}))
