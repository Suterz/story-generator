import json
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from arithmetic import calculate
from graphics import expand_counter_rows
from spoken_money import spoken_money
from storygen import SKILL, compile_story, main, read, render, validate, validate_native


def draft():
    story = read(SKILL.parent / "annotated-example.json")
    story["voice_profile"] = "heart"
    return story


class WriterTests(unittest.TestCase):
    def test_compiles_visible_prediction_and_parented_spoken_cue(self):
        story = draft()
        story["beats"][1].pop("parent")
        result = validate(compile_story(story))
        self.assertEqual(result["beats"][1]["parent"], result["beats"][0]["id"])
        self.assertEqual(result["beats"][1]["cue"]["utterance_id"], "reveal")
        self.assertEqual(result["instructional"]["required_facts"],
                         ["first-blue", "second-blue", "four-gaps"])

    def test_rejects_absent_clues_and_nonspoken_answer(self):
        story = draft()
        story["beats"][0]["panel"]["overlays"] = []
        with self.assertRaisesRegex(ValueError, "actual visible clues"):
            compile_story(story)
        story = compile_story(draft())
        story["instructional"]["spoken_answer_phrases"] = ["a different answer"]
        with self.assertRaisesRegex(ValueError, "verbatim"):
            validate(story)

    def test_arithmetic_and_currency_are_exact(self):
        self.assertEqual(calculate("8 / 5"), Fraction(8, 5))
        self.assertEqual(calculate("4 + 12 - 19"), -3)
        with self.assertRaises(ValueError):
            calculate("round(1.2)")
        self.assertEqual(spoken_money("$1.60 and $0.05"), "one dollar and sixty cents and five cents")

    def test_count_rows_have_distinct_visible_ids(self):
        panel = {"counter_rows": [{"id": "items", "count": 3, "y": .4, "label": "THREE"}]}
        expand_counter_rows(panel)
        marks = panel["overlays"]
        self.assertEqual([m["fact"] for m in marks[:3]], ["items-1", "items-2", "items-3"])
        self.assertEqual(len({m["at"][0] for m in marks[:3]}), 3)

    def test_partial_native_configuration_is_not_silently_skipped(self):
        with patch.dict("os.environ", {"STORYGEN_VALIDATOR_PYTHON": "/some/python"}, clear=True):
            with self.assertRaisesRegex(ValueError, "both"):
                validate_native({})

    def test_native_cli_preserves_venv_interpreter_symlink(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            python = root / "python"
            python.symlink_to("/usr/bin/python3")
            argv = ["storygen", "write", "brief.json", "--out", str(root / "out"),
                    "--validator-python", str(python), "--frames-repo", folder, "--video-repo", folder]
            def check(_):
                import os
                self.assertEqual(os.environ["STORYGEN_VALIDATOR_PYTHON"], str(python))

            with patch.dict("os.environ", clear=True), patch("sys.argv", argv), patch("storygen.write", check):
                main()

    def test_lost_acknowledgement_resumes_with_get_only(self):
        with TemporaryDirectory() as folder:
            args = SimpleNamespace(out=Path(folder), video_url="http://renderer")
            with patch("storygen.request", side_effect=TimeoutError) as call:
                with self.assertRaises(TimeoutError):
                    render(args, {"title": "fixture"})
                self.assertEqual(call.call_args.args[0], "http://renderer/v2/renders")
            key = read(args.out / "submission.json")["key"]
            with patch("storygen.request", return_value=json.dumps({"state": "needs_review"}).encode()) as call:
                status = render(args, {"title": "fixture"})
                call.assert_called_once_with(f"http://renderer/v2/submissions/{key}")
                self.assertEqual(status["state"], "needs_review")


if __name__ == "__main__":
    unittest.main()
