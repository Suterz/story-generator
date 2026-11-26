import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from communication import NeedsInput, UnsupportedBrief, check_supplied_authority, intent_hash, normalize
from storygen import SIGNATURES, generation_schema, load_brief

ROOT = Path(__file__).parent
EXAMPLES = ROOT / "examples/carriage"


class CommunicationTests(unittest.TestCase):
    def test_complete_structured_request_bypasses_extraction(self):
        with TemporaryDirectory() as directory, patch("storygen.writer", side_effect=AssertionError):
            args = SimpleNamespace(input=EXAMPLES / "wayfinding.json", out=Path(directory), raw_text=False)
            result, generic = load_brief(args, None, {})
            self.assertTrue(generic)
            self.assertEqual(result["language"], "en")
            original = json.loads(args.input.read_text())
            for field, value in original.items():
                self.assertEqual(result[field], value)
            evidence = json.loads((args.out / "normalization.json").read_text())
            self.assertEqual(evidence["intent_sha256"], intent_hash(result))

    def test_missing_input_is_typed_and_reusable(self):
        brief, _ = normalize(json.loads((EXAMPLES / "missing-rules.json").read_text()), SIGNATURES)
        with self.assertRaises(NeedsInput) as raised:
            check_supplied_authority(brief)
        self.assertFalse(raised.exception.result["render_submitted"])
        self.assertIn("phone calls", raised.exception.result["missing"][0]["question"])
        brief["source_notes"].append({"kind": "fact", "text": "Passengers must make phone calls outside this carriage."})
        check_supplied_authority(brief)
        for case in ("wayfinding", "empathy"):
            valid, _ = normalize(json.loads((EXAMPLES / f"{case}.json").read_text()), SIGNATURES)
            check_supplied_authority(valid)

    def test_only_generic_generation_makes_prediction_optional(self):
        self.assertIn("instructional", generation_schema()["required"])
        self.assertNotIn("instructional", generation_schema(communication=True)["required"])

    def test_request_overrides_are_checked(self):
        brief = json.loads((EXAMPLES / "wayfinding.json").read_text())
        with self.assertRaises(UnsupportedBrief):
            normalize({**brief, "language": "de"}, SIGNATURES)
        self.assertEqual(normalize({**brief, "max_duration_ms": 13000}, SIGNATURES)[0]["max_duration_ms"], 13000)
