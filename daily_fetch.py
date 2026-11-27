#!/usr/bin/env python3
"""Opt-in publisher broker. Exact allowlisted hosts, no redirects or ambient proxies."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from socket import timeout
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class PublisherPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden.append(tag)

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.chunks.append(" ".join(data.split()))


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download(url, *, limit, types, permitted):
    parsed = urlsplit(url)
    agent = os.getenv("DAILY_HTTP_AGENT")
    if (parsed.scheme != "https" or parsed.netloc != parsed.hostname or parsed.hostname not in permitted
            or not agent):
        return {"error": "publisher_not_configured", "requests": 0}
    opener = build_opener(ProxyHandler({}), NoRedirects())
    request = Request(url, headers={"User-Agent": agent})
    for attempt in (1, 2):
        try:
            with opener.open(request, timeout=12) as response:
                mime = response.headers.get_content_type()
                data = response.read(limit + 1)
                if len(data) > limit or mime not in types:
                    return {"error": "unsupported_document", "requests": attempt}
                return {"data": data, "page": response.url, "requests": attempt, "mime": mime,
                        "charset": response.headers.get_content_charset() or "utf-8"}
        except HTTPError as error:
            if error.code not in {500, 502, 503, 504} or error.headers.get("Retry-After"):
                return {"error": f"http_{error.code}", "requests": attempt}
        except (timeout, URLError):
            pass
    return {"error": "inaccessible", "requests": 2}


def fetch(url):
    hosts = json.loads(os.environ.get("DAILY_PUBLISHERS", "{}"))
    response = download(url, limit=1024*1024, types={"text/plain", "text/html"}, permitted=hosts)
    if "error" in response:
        return response
    data = response.pop("data")
    text = data.decode(response.pop("charset"), errors="replace")
    if response.pop("mime") == "text/html":
        parser = PublisherPage()
        parser.feed(text)
        text = "\n".join(parser.chunks)
    return {**response, "text": text, "publisher": hosts[urlsplit(url).hostname],
            "retrieved": datetime.now(timezone.utc).date().isoformat(),
            "sha256": hashlib.sha256(data).hexdigest()}


def discover(query):
    params = urlencode({"query.bibliographic": query, "rows": 6, "select": "URL,resource,link"})
    response = download("https://api.crossref.org/v1/works?" + params, limit=128*1024,
                        types={"application/json"}, permitted={"api.crossref.org"})
    if "error" in response:
        return response
    hosts = json.loads(os.environ.get("DAILY_PUBLISHERS", "{}"))
    links = []
    for item in json.loads(response["data"])["message"]["items"]:
        primary = item.get("resource", {}).get("primary", {}).get("URL", "")
        for candidate in [primary, item.get("URL", ""), *(row.get("URL", "") for row in item.get("link", []))]:
            if urlsplit(candidate).hostname in hosts and candidate not in links:
                links.append(candidate)
    return {"pages": links[:2], "requests": response["requests"], "provider": "Crossref"}


if __name__ == "__main__":
    print(json.dumps(discover(sys.argv[2]) if sys.argv[1] == "--discover" else fetch(sys.argv[1])))
