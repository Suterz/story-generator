"""Claim-scoped evidence. HTTP is confined to an explicitly configured broker."""
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def persist(path, value):
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def check_source(claim, source, as_of):
    for field in ("publisher", "page", "locator", "passage", "context"):
        if not source.get(field):
            return f"missing_{field}"
    if source["passage"] not in source["context"]:
        return "passage_not_in_context"
    for dimension, expected in claim.get("scope", {}).items():
        if source.get("scope", {}).get(dimension) != expected:
            return f"wrong_{dimension}"
    if "max_age_days" in claim:
        try:
            age = (as_of - date.fromisoformat(source["retrieved"])).days
        except (KeyError, ValueError):
            return "undated"
        if not 0 <= age <= claim["max_age_days"]:
            return "stale"
    return None


class Retrieval:
    def __init__(self, program, receipt):
        self.program = program
        self.receipt = receipt
        self.events = []
        self.deadline = None
        persist(receipt, self.events)

    def fetch(self, url):
        return self.call([url], {"page": url}, 6)

    def discover(self, query):
        return self.call(["--discover", query], {"discovery": "Crossref"}, 2)

    def call(self, arguments, event, cap):
        if not self.program:
            return {"error": "offline"}
        if self.deadline is None:
            self.deadline = time.monotonic() + 120
        count = sum(("page" in row) == ("page" in event) for row in self.events)
        if count >= cap or self.deadline <= time.monotonic():
            return {"error": "retrieval_budget"}
        event["outcome"] = "started"
        self.events.append(event)
        persist(self.receipt, self.events)
        try:
            response = subprocess.run([self.program, *arguments], capture_output=True, text=True,
                                      timeout=min(38, self.deadline - time.monotonic()), check=True)
            result = json.loads(response.stdout)
        except (subprocess.SubprocessError, OSError, ValueError):
            result = {"error": "inaccessible"}
        event.update(outcome=result.get("error", "downloaded"), requests=result.get("requests"))
        persist(self.receipt, self.events)
        return result


def resolve(claim, supplied, cached, today, assess, retrieval, research=None):
    decisions = []
    if claim.get("caller_only") and not supplied:
        return decisions, "needs_input", []
    for route, pool in (("supplied", supplied), ("cached", [] if claim.get("caller_only") else cached)):
        approved, contradicted = [], []
        for source in pool:
            problem = check_source(claim, source, today)
            opinion = problem or assess(claim, source)
            decisions.append({"route": route, "source": source, "decision": opinion})
            if opinion == "supports":
                approved.append(source)
            if opinion == "contradicts":
                contradicted.append(source)
        if contradicted:
            return decisions, "contradictory", []
        if approved:
            return decisions, route, approved
    if claim.get("caller_only"):
        return decisions, "needs_input", []
    approved, contradicted = [], []
    pages = claim.get("candidate_pages", [])
    if not pages and research:
        discovery = research(claim)
        pages = discovery.get("pages", [])
        decisions.append({"route": "discovery", "decision": discovery.get("error", "searched"),
                          "provider": discovery.get("provider"), "candidates": pages})
    for url in pages[:2]:
        document = retrieval.fetch(url)
        if "error" in document:
            decisions.append({"route": "fresh", "page": url, "decision": document["error"]})
            continue
        candidate = assess(claim, document, extract=True)
        passage = candidate.get("passage", "")
        offset = document["text"].find(passage) if passage else -1
        if offset < 0:
            decisions.append({"route": "fresh", "page": url, "decision": "passage_not_found"})
            continue
        source = {**candidate, "origin": "retrieved", "publisher": document["publisher"],
                  "page": document["page"], "retrieved": document["retrieved"],
                  "document_sha256": document["sha256"], "span": [offset, offset + len(passage)],
                  "context": document["text"][max(0, offset-400):offset+len(passage)+400]}
        opinion = check_source(claim, source, today) or assess(claim, source)
        decisions.append({"route": "fresh", "source": source, "decision": opinion})
        if opinion == "supports":
            approved.append(source)
        if opinion == "contradicts":
            contradicted.append(source)
    if contradicted:
        return decisions, "contradictory", []
    return decisions, "fresh" if approved else "unsupported", approved


def cache_path(root, claim):
    return Path(root) / (digest({key: claim.get(key) for key in ("text", "scope")}) + ".json")


def cache_root():
    return Path(os.getenv("DAILY_SOURCE_CACHE", Path.home() / "ai/autonomous-daily/source-cache"))
