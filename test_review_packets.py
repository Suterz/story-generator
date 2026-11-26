from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from communication_score import score
from review_packets import collect
from storygen import read, save


class ReviewPacketTests(unittest.TestCase):
    def test_withheld_draft_retains_first_narration_without_model_label(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "model-a"
            row = run / "C01"
            row.mkdir(parents=True)
            save(run / "freeze.json", {"case_ids": ["C01"], "model": "model-a"})
            save(row / "brief.json", {"objective": "Help the visitor find the door"})
            save(row / "oracle.json", {"answer": "the door with the circle"})
            save(row / "writer-attempt-0.json", {"response": {"choices": [{"message":
                 {"content": '{"script":[{"id":"intro","text":"Look for the circle."}]}'}}]}})
            collect([run], root / "review", "fixture")
            packet, = (root / "review/blind").iterdir()
            self.assertEqual(read(packet / "first-script.json"), [{"text": "Look for the circle.", "caption": None}])
            self.assertFalse((packet / "script.json").exists())
            self.assertFalse((packet / "video.mp4").exists())
            self.assertNotIn("model-a", packet.name)
            save(row / "first-script-judgment.json", {"verdict": "meets_brief", "first_attempt_sha256": "stale"})
            with self.assertRaisesRegex(ValueError, "does not bind"):
                score(run)
