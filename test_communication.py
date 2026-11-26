import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from communication import NeedsInput, UnsupportedBrief, check_supplied_authority, extract, intent_hash, normalize
from communication_sweep import corpus, digest
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
        self.assertNotIn("style_ref_ids", generation_schema(communication=True)["properties"]["visual"]["properties"])
        self.assertNotIn("checks", generation_schema(communication=True)["properties"]["visual"]["properties"])

    def test_request_overrides_are_checked(self):
        brief = json.loads((EXAMPLES / "wayfinding.json").read_text())
        with self.assertRaises(UnsupportedBrief):
            normalize({**brief, "language": "de"}, SIGNATURES)
        self.assertEqual(normalize({**brief, "max_duration_ms": 13000}, SIGNATURES)[0]["max_duration_ms"], 13000)

    def test_rough_round_trip_preserves_an_explicit_prohibition(self):
        rough = (EXAMPLES / "rough.txt").read_text()
        structured = json.loads((EXAMPLES / "wayfinding.json").read_text())
        brief = {**structured, "audience": "commuters on the platform", "tone": "calm and direct",
                 "objective": structured["objective"].rstrip("."), "takeaway": structured["takeaway"].rstrip("."),
                 "source_notes": [{"kind": "fact", "text": structured["source_notes"][0]["text"].rstrip(".")}]}
        provenance = {f"/{k}": {"origin": "supplied", "excerpt": rough.split(". ")[0]}
                      for k in brief if k not in {"schema_version", "source_notes", "tone"}}
        provenance["/tone"] = {"origin": "supplied", "excerpt": "Calm and direct"}
        provenance["/source_notes/0"] = {"origin": "supplied", "excerpt": brief["source_notes"][0]["text"]}
        actual, origins = extract(rough, lambda _prompt: {"brief": brief, "provenance": provenance}, SIGNATURES)
        self.assertEqual(actual, normalize(structured, SIGNATURES)[0])
        self.assertEqual(origins["/source_notes/1"]["excerpt"], "Do not state carriage rules.")

    def test_public_partitions_are_frozen_with_an_objective_only_pair(self):
        benchmark = ROOT / "benchmark/communication"
        freeze = json.loads((benchmark / "freeze.json").read_text())
        dev = corpus(benchmark / "development.tsv", legacy=True)
        validation = corpus(benchmark / "validation.tsv")
        self.assertEqual(len(dev), 60)
        self.assertEqual(len(validation), 20)
        self.assertEqual(len([key for key in dev if not key.startswith("D")]), 20)
        self.assertTrue({x[-1] for x in dev.values()}.isdisjoint(x[-1] for x in validation.values()))
        for name in ("development", "validation"):
            self.assertEqual(freeze["sha256"][name], digest(benchmark / f"{name}.tsv"))
        a, b = (json.loads((EXAMPLES / f"{case}.json").read_text()) for case in ("wayfinding", "empathy"))
        self.assertNotEqual(a.pop("objective"), b.pop("objective"))
        self.assertEqual(a, b)
