from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from daily_evidence import persist
from opening_score import score, sha
from opening_review import heard_numbers
from opening_trial import compile_preview, repair_focus


class OpeningTests(unittest.TestCase):
    def test_spoken_equivalent_does_not_change_its_numeric_value(self):
        self.assertEqual(heard_numbers("seventy-five kilowatt-hours"), {75})
        self.assertEqual(heard_numbers("75 kWh"), {75})
        self.assertEqual(heard_numbers("75.5 kWh"), {75.5})

    def test_focus_repair_keeps_reading_values_and_speech(self):
        meters = [{"object": key, "readings": [{"label": "return", "display": str(value),
                                              "focus": key == "A"}]}
                  for key, value in (("A", 75), ("B", 48))]
        request = {"script": [{"text": "B returns forty-eight"}], "beats": [
            {"id": "cut", "panel": {"daily": {"data": {"meters": meters}}}}]}
        repair_focus(request, {"beat": "cut", "object": "B", "label": "return"})
        self.assertEqual([m["readings"][0]["focus"] for m in meters], [False, True])
        self.assertEqual([m["readings"][0]["display"] for m in meters], ["75", "48"])
        self.assertEqual(request["script"][0]["text"], "B returns forty-eight")

    def test_compiles_phone_preview_with_spoken_captions(self):
        section = {"narration": "Look at this clock.", "visible": "A clock", "claim_ids": ["fact-1"],
                   "kind": "illustration", "visual_data": {}}
        request = compile_preview({"topic": "Time", "objective": "Compare clocks"},
                                  {"promise": "Time changes", "states": [section]*3}, {"fact-1"}, "drama3-F")
        self.assertEqual(request["script"][0]["caption"], section["narration"])
        self.assertEqual(request["beats"][0]["cue"], {"ms": 0})
        self.assertEqual(request["voice_profile"], "drama3-F")
        self.assertTrue(request["opening_preview"])

    def test_correct_rejection_with_invented_reason_is_not_a_diagnosis(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "01"
            result.mkdir()
            labels, seal = root / "labels.json", root / "seal.json"
            persist(labels, {"01": {"quality": "bad", "defect": "early_reveal", "interval_seconds": [1, 2]}})
            persist(seal, {"labels_sha256": sha(labels), "clips": {"01": "filehash"},
                           "rubric": "test", "timing_tolerance_seconds": .5})
            persist(result / "local-opening-verdict.json", {"mp4_sha256": "filehash", "status": "failed",
                    "code": "wrong_value", "start_seconds": 1.5})
            counts = score(seal, labels, root)["counts"]
            self.assertEqual(counts["bad_accepted"], 0)
            self.assertEqual(counts["correctly_localized"], 0)
            self.assertEqual(counts["incorrect_diagnosis_on_withholds"], 1)
