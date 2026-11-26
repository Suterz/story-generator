import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from communication import NeedsInput, UnsupportedBrief, check_supplied_authority, extract, intent_hash, normalize
from communication_sweep import corpus, digest
from storygen import SIGNATURES, bind_opening, bind_overlay_removals, check_communication_anchors, check_meaningful_overlays, check_visual_answers, communication_skill, compile_story, compile_surfaces, generation_schema, load_brief, validate

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
        self.assertNotIn("instructional", generation_schema(communication=True, prediction=False)["properties"])
        self.assertNotIn("style_ref_ids", generation_schema(communication=True)["properties"]["visual"]["properties"])
        self.assertNotIn("checks", generation_schema(communication=True)["properties"]["visual"]["properties"])
        self.assertNotIn("canvas", generation_schema(communication=True)["properties"]["visual"]["properties"])

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

    def test_overlay_uses_the_accepted_parent_surface(self):
        story = json.loads((EXAMPLES / "contract-story.json").read_text())
        check_communication_anchors(story)
        story["beats"][1]["panel"]["overlays"][0]["at"] = "made-up.face"
        with self.assertRaisesRegex(ValueError, "is not grounded"):
            check_communication_anchors(story)

    def test_binary_check_leaves_the_predicate_in_the_question(self):
        story = json.loads((EXAMPLES / "contract-story.json").read_text())
        check_visual_answers(story)
        check = story["beats"][0]["panel"]["clean_checks"][1]
        check["expected"] = "Yes, the sign is visible and free of obstructions."
        with self.assertRaisesRegex(ValueError, "all required visual details in the question"):
            check_visual_answers(story)

    def test_empty_reveal_cannot_claim_a_new_mark_but_real_removals_work(self):
        story = json.loads((EXAMPLES / "contract-story.json").read_text())
        check_meaningful_overlays(story)
        a, b = [beat["panel"] for beat in story["beats"]]
        mark = b.pop("overlays")
        with self.assertRaisesRegex(ValueError, "actual overlay data"):
            check_meaningful_overlays(story)
        a["overlays"] = mark
        b["op"] = "clear_overlays"
        check_meaningful_overlays(story)
        bind_overlay_removals(story)
        self.assertEqual(b["op"], "overlay_only")

    def test_grammar_requires_graphics_or_explicit_removal_for_overlay_only(self):
        from jsonschema import Draft202012Validator
        schema = generation_schema(communication=True, prediction=False)
        draft = json.loads((EXAMPLES / "contract-story.json").read_text())
        for key in ("voice_profile", "max_ms"):
            draft.pop(key)
        draft["visual"].pop("visual_signature")
        opening = draft["beats"].pop(0)
        opening.pop("cue")
        opening["panel"].pop("op")
        draft["opening"] = opening
        draft["script"][1].pop("caption_not_before_beat")
        overlay = draft["beats"][0]["panel"]["overlays"][0]
        overlay.pop("at")
        overlay["surface"] = "The plate on the train door"
        d = Draft202012Validator(schema)
        self.assertTrue(d.is_valid(draft), list(d.iter_errors(draft)))
        del overlay["surface"]
        overlay["at"] = "invented-door-id"
        self.assertFalse(d.is_valid(draft))
        panel = draft["beats"][0]["panel"]
        panel["overlays"] = []
        self.assertFalse(d.is_valid(draft))
        panel.pop("overlays")
        panel["op"] = "clear_overlays"
        self.assertTrue(d.is_valid(draft), list(d.iter_errors(draft)))

    def test_explicit_skill_version_preserves_its_own_identity(self):
        self.assertEqual(communication_skill("v6").parent.name, "v6")
        with self.assertRaisesRegex(ValueError, "must be"):
            communication_skill("../lesson-writer/v4")

    def test_cue_correction_identifies_the_actual_spoken_ids(self):
        story = json.loads((EXAMPLES / "contract-story.json").read_text())
        story["beats"][1]["cue"] = {"at_utterance_start": "intro"}
        with self.assertRaisesRegex(ValueError, "actual script ID: platform, sign"):
            compile_story(story)

    def test_writer_surface_compiles_into_the_existing_frame_contract(self):
        story = json.loads((EXAMPLES / "contract-story.json").read_text())
        story["beats"][0]["panel"].pop("anchors")
        overlay = story["beats"][1]["panel"]["overlays"][0]
        overlay.pop("at")
        overlay["surface"] = "Whole blank sign plate on the train door"
        compiled = validate(compile_story(compile_surfaces(story)))
        parent, child = [b["panel"] for b in compiled["beats"]]
        target = child["overlays"][0]["at"]
        self.assertTrue(target.endswith(".face"))
        self.assertEqual(parent["anchors"][target], "Whole blank sign plate on the train door")
        self.assertIn("Include this unobstructed surface in the clean art: Whole blank sign plate on the train door.", parent["instruction"])
        self.assertNotIn("☾", parent["instruction"])
        self.assertNotIn("surface", child["overlays"][0])

    def test_compiled_count_circles_cannot_stand_in_for_a_generated_door_mark(self):
        story = json.loads((EXAMPLES / "contract-story.json").read_text())
        story["beats"][1]["panel"]["counter_rows"] = [{"id": "mark", "count": 1, "y": 0.5, "label": "crescent"}]
        with self.assertRaisesRegex(ValueError, "cannot represent a sign"):
            compile_surfaces(story)
        story["beats"][0]["panel"]["paper_scene"] = True
        compile_surfaces(story)

    def test_opening_is_compiled_without_inventing_a_spoken_cue(self):
        draft = json.loads((EXAMPLES / "contract-story.json").read_text())
        opening = draft["beats"].pop(0)
        original_cue = draft["beats"][0]["cue"].copy()
        opening.pop("cue")
        opening["panel"].pop("op")
        draft["opening"] = opening
        result = validate(compile_story(bind_opening(draft)))
        self.assertEqual(result["beats"][0]["cue"], {"ms": 0})
        self.assertEqual(result["beats"][0]["panel"]["op"], "new_scene")
        self.assertEqual(result["beats"][1]["cue"], original_cue)
        schema = generation_schema(communication=True)
        self.assertIn("opening", schema["required"])
        self.assertNotIn("cue", schema["properties"]["opening"]["properties"])
        self.assertNotIn("overlays", schema["properties"]["opening"]["properties"]["panel"]["required"])
        self.assertNotIn("visual_signature", schema["properties"]["visual"]["required"])
        self.assertIn("visual_signature", generation_schema()["properties"]["visual"]["required"])
