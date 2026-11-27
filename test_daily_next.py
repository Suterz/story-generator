from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from daily import adapt, extract_claims
from daily_evidence import persist
from daily_flow import ordinary_run, read


class OrdinaryDaily(unittest.TestCase):
    def test_minimal_input_needs_no_visual_metadata(self):
        raw = {"schema_version": "daily/2", "topic": "A topic", "audience": "Adults",
               "objective": "Understand the comparison"}
        self.assertEqual(adapt(raw, False), raw)

    def test_unindexed_caller_evidence_is_still_assessed(self):
        intent = {"claims": [{"text": "The two readings differ", "essential": True,
                              "scope": {}, "fact_indices": [], "caller_only": False}]}
        claim, = extract_claims(intent, ["One reads 10; the other reads 8."])
        self.assertEqual(claim["sources"][0]["passage"], "One reads 10; the other reads 8.")

    def test_automatic_revision_preserves_first_outcome(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            input_ = root / "input.json"
            freeze = root / "freeze"
            input_.write_text("{}")
            freeze.write_text("{}")
            args = Namespace(out=root, input=input_, voice="heart", model="mistral-small",
                             video_url="http://localhost", runtime="runtime", models="models",
                             episode_skill="routed", daily=True)
            calls = []

            def run(local):
                calls.append(getattr(local, "repair_feedback", None))
                result = {"status": "withheld", "reason": "cue mismatch", "automatic_revisions": [],
                          "renderer": {"phase": "alignment"}}
                if len(calls) > 1:
                    result = {"status": "needs_review", "reason": "visual uncertainty", "automatic_revisions": []}
                persist(local.out / "first-outcome.json", result)

            with patch.dict("os.environ", {"DAILY_FREEZE": str(freeze)}), patch("daily.run_daily", side_effect=run):
                ordinary_run(args)
            self.assertEqual(calls, [None, "cue mismatch"])
            self.assertEqual(read(root / "first-outcome.json")["reason"], "cue mismatch")
            self.assertEqual(read(root / "terminal-outcome.json")["automatic_revision_count"], 1)
