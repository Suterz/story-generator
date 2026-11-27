from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from daily_evidence import Retrieval, resolve
from storygen import render


class TestEvidence(unittest.TestCase):
    def setUp(self):
        self.claim = {"text": "Travel time fell for night riders in 2024.", "scope": {
            "population": "night riders", "period": "2024"},
            "candidate_pages": ["https://example.org/report"], "max_age_days": 1}
        self.source = {"passage": self.claim["text"], "context": self.claim["text"],
                       "page": "https://example.org/report", "locator": "Table 1", "publisher": "Example",
                       "scope": self.claim["scope"], "retrieved": "2026-11-27", "origin": "caller"}
        self.today = date(2026, 11, 27)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.retrieval = Retrieval(None, Path(self.directory.name) / "requests.json")

    def test_complete_pack_is_offline(self):
        class NeverFetch:
            def fetch(self, url):
                raise AssertionError("complete packs must not call retrieval")

        decisions, route, sources = resolve(self.claim, [self.source], [], self.today,
                                            lambda *_: "supports", NeverFetch())
        self.assertEqual(route, "supplied")
        self.assertEqual(sources, [self.source])

    def test_caller_only_cannot_use_cache(self):
        _, route, _ = resolve({**self.claim, "caller_only": True}, [], [self.source], self.today,
                              lambda *_: "supports", self.retrieval)
        self.assertEqual(route, "needs_input")

    def test_wrong_scope_stale_and_inaccessible(self):
        class Denied:
            def fetch(self, url):
                return {"error": "http_403"}

        bad = [{**self.source, "scope": {**self.source["scope"], field: "wrong"}}
               for field in ("population", "period")]
        bad.append({**self.source, "retrieved": "2026-11-22"})
        decisions, route, sources = resolve(self.claim, bad, [], self.today, lambda *_: "supports", Denied())
        self.assertEqual([row["decision"] for row in decisions],
                         ["wrong_population", "wrong_period", "stale", "http_403"])
        self.assertEqual((route, sources), ("unsupported", []))

    def test_contradiction_cannot_be_outvoted(self):
        opposing = {**self.source, "passage": "It rose.", "context": "It rose."}
        decisions, route, sources = resolve(self.claim, [self.source, opposing], [], self.today,
            lambda claim, source: "supports" if claim["text"] == source["passage"] else "contradicts",
            self.retrieval)
        self.assertEqual(len(decisions), 2)
        self.assertEqual((route, sources), ("contradictory", []))

    def test_exact_retrieved_passage_keeps_provenance(self):
        source = self.source

        class Publisher:
            def fetch(self, url):
                return {"text": "Lead. " + source["passage"], "page": url, "publisher": "Example",
                        "retrieved": "2026-11-27", "sha256": "fixture"}

        def assess(claim, _, extract=False):
            if extract:
                return {"passage": source["passage"], "locator": "Table 1", "scope": claim["scope"]}
            return "supports"

        _, route, sources = resolve(self.claim, [], [], self.today, assess, Publisher())
        self.assertEqual(route, "fresh")
        self.assertEqual(sources[0]["origin"], "retrieved")
        self.assertEqual(sources[0]["span"][0], 6)


class TestResume(unittest.TestCase):
    def test_crash_between_client_receipt_and_post_reuses_key(self):
        with TemporaryDirectory() as folder:
            args = SimpleNamespace(out=Path(folder), video_url="http://localhost")
            story = {"chapter_starts": ["a", "b"]}
            with patch("storygen.request", side_effect=ConnectionError):
                with self.assertRaises(ConnectionError):
                    render(args, story)
            info = (args.out / "submission.json").read_text()
            calls = []

            def request(url, data=None, headers=None):
                calls.append((url, data, headers))
                if data is None:
                    raise HTTPError(url, 404, "not submitted", None, None)
                return b'{"state":"needs_review"}'

            with patch("storygen.request", side_effect=request):
                self.assertEqual(render(args, story)["state"], "needs_review")
            self.assertEqual((args.out / "submission.json").read_text(), info)
            self.assertTrue(calls[0][0].endswith(calls[1][2]["Idempotency-Key"]))

    def test_lost_post_response_recovers_remote_receipt_without_repost(self):
        with TemporaryDirectory() as folder:
            args = SimpleNamespace(out=Path(folder), video_url="http://localhost")
            with patch("storygen.request", side_effect=ConnectionError):
                with self.assertRaises(ConnectionError):
                    render(args, {})
            with patch("storygen.request", return_value=b'{"state":"needs_review"}') as request:
                render(args, {})
                self.assertEqual(request.call_count, 1)
                self.assertIn("/v2/submissions/", request.call_args.args[0])
