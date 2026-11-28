from copy import deepcopy
import json
from pathlib import Path
import unittest

from brief_enforcement.lesson import compile_lesson, verify_order, verify_transfer
from brief_enforcement.readiness import inspect, plan_errors


class Readiness(unittest.TestCase):
    def setUp(self):
        self.example = Path(__file__).parent / "examples/battery.json"
        self.brief = json.loads(self.example.read_text())

    def test_ready_complete_and_vague_rejected(self):
        self.assertEqual(inspect(self.brief)["status"], "ready")
        sparse = {"schema_version": "daily/2", "topic": "Batteries", "audience": "Everyone",
                  "objective": "Explain batteries."}
        self.assertEqual(inspect(sparse)["status"], "needs_input")
        filled = {**self.brief, "objective": "Explain batteries.", "audience": "Everyone"}
        self.assertEqual(inspect(filled)["status"], "needs_input")

    def test_critical_contradiction_and_research_gap(self):
        wrong = deepcopy(self.brief)
        wrong["comparison"]["answer"] = "Battery A"
        self.assertEqual(inspect(wrong)["status"], "withhold")
        wrong = deepcopy(self.brief)
        wrong["comparison"]["objects"][1]["returned"] = 49
        self.assertEqual(inspect(wrong)["status"], "withhold")
        gap = deepcopy(self.brief)
        gap["facts"][0]["kind"] = "public_gap"
        self.assertEqual(inspect(gap)["status"], "needs_research")

    def test_conclusion_cannot_move_ahead_of_proof(self):
        lesson, plan = compile_lesson(self.brief, "drama3-A")
        self.assertFalse(plan_errors(self.brief, plan))
        early = [*plan[:2], plan[3], plan[2]]
        self.assertIn("conclusion before evidence", " ".join(plan_errors(self.brief, early)))
        self.assertNotIn("Share returned", json.dumps(lesson["beats"][2]))
        self.assertIn("75/100 = 75%", json.dumps(lesson["beats"][3]))
        self.assertNotIn("made better use", lesson["script"][3]["text"])
        self.assertIn("Battery B made better use", lesson["script"][4]["text"])

    def test_changed_order_and_winner_are_preserved(self):
        brief = json.loads(self.example.with_name("battery-swapped.json").read_text())
        self.assertEqual(inspect(brief)["status"], "ready")
        story, _ = compile_lesson(brief, "drama3-A")
        self.assertIn("Battery B returns eighty-four", story["script"][0]["text"])
        self.assertIn("Battery A made better use", story["script"][4]["text"])

    def test_duration_preference_is_separate_from_hard_range(self):
        story, _ = compile_lesson(self.brief, "drama3-A")
        self.assertEqual(story["min_ms"], 20000)
        self.brief["duration"]["kind"] = "hard"
        story, _ = compile_lesson(self.brief, "drama3-A")
        self.assertEqual(story["min_ms"], 35000)

    def test_a_complete_brief_without_a_supported_route_is_not_queued(self):
        brief = json.loads(self.example.with_name("shadow.json").read_text())
        result = inspect(brief)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["queueable"])

    def test_exact_transfer_answer_binds_to_changed_readings(self):
        baseline = inspect(self.brief)
        self.assertTrue(baseline["queueable"])
        wrong = deepcopy(self.brief)
        wrong["transfer"]["percent"] = 75
        result = inspect(wrong)
        self.assertEqual(result["status"], "withhold")
        self.assertFalse(result["queueable"])
        self.assertEqual(result["issues"][0]["field"], "/transfer/percent")
        repeated = deepcopy(self.brief)
        repeated["transfer"] = {"input": 100, "returned": 75, "percent": 75}
        self.assertEqual(inspect(repeated)["status"], "needs_input")
        self.brief["transfer"] = {"input": 40, "returned": 20, "percent": 50}
        story, _ = compile_lesson(self.brief, "drama3-A")
        self.assertIn("takes in forty and returns twenty", story["script"][-2]["text"])
        self.assertEqual(story["script"][-1]["text"], "Fifty percent. Divide twenty by forty.")

    def test_question_is_not_an_early_declaration(self):
        story, _ = compile_lesson(self.brief, "drama3-A")
        panels = [{}, {}, {}, {"daily_visual": {"proof": {
            "meters": story["beats"][3]["panel"]["daily"]["data"]["meters"]}}}]
        segment = {"cues": [{"seconds": i*3} for i in range(5)]}
        def check(text):
            return verify_order(self.brief, segment, [{"word": text, "end": 2},
                                {"word": "Battery B made better use of its input.", "start": 12, "end": 14}],
                                {"panels": panels})
        self.assertFalse(check("Which made better use of its input?"))
        self.assertEqual(len(check("Battery B made better use of its input.")), 1)

    def test_delivered_transfer_requires_grounded_operands_percent_and_division(self):
        decoded = {"duration": 60, "cues": [{"id": "lesson-6", "seconds": 40},
                                           {"id": "lesson-7", "seconds": 50}]}
        question = "A third battery takes in 50 and returns 40kWh. What share is that?"

        def check(answer, prompt=question):
            words = [{"word": prompt, "start": 40, "end": 49},
                     {"word": answer, "start": 50, "end": 58}]
            return verify_transfer(self.brief, decoded, words)

        self.assertFalse(check("80 %. Divide forty by fifty."))
        self.assertFalse(check("Eighty percent. 40 divided by 50 is four fifths."))
        for wrong in ("81%. Divide forty by fifty.", "80.5%. Divide forty by fifty.",
                      "80. Divide forty by fifty.", "80%. Divide fifty by forty."):
            self.assertEqual(check(wrong)[0]["start_seconds"], 50)
        self.assertEqual(check("80%. Divide forty by fifty.", question.replace("50", "60"))[0]["start_seconds"], 40)
