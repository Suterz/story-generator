from copy import deepcopy
import json
from pathlib import Path
import unittest

from brief_enforcement.lesson import compile_lesson
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
