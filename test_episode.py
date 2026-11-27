import math
import unittest
import json
from copy import deepcopy
from pathlib import Path

from episode import check_clock_explanation, check_transfer_explanation, compile_chapter, skill_for
from episode_graphics import CITATION_PACKET, bank, citation, clock, ledger_at, light_events
from source_pack import evidence_for
from transfer_graphics import project, queue_at


class EvidenceTests(unittest.TestCase):
    def test_transfer_state_rejects_inconsistent_narration(self):
        for fixture, stage, sentence in (
            ("queue", "next", "D arrived right after B left."),
            ("queue", "next", "D showed up right after B left."),
            ("queue", "second", "D arrived just as A left, not when B started."),
            ("queue", "delay", "Only C is waiting."),
            ("shutter", "short", "The short exposure shows forty pixels."),
            ("study", "mismatch", "Guo and colleagues wrote about viewing time."),
            ("seasons", "angle", "The sunlight scatters at this angle."),
            ("map", "globe", "They’re the same size in reality."),
            ("salary", "transfer", "The remaining two now average eighty thousand dollars."),
        ):
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                check_transfer_explanation(fixture, stage, sentence)
        check_transfer_explanation("shutter", "comparison", "The second streak is forty pixels.")
        check_transfer_explanation("map", "patches", "On Earth, they’re the same size.")
        check_transfer_explanation("seasons", "angle", "The distance to the Sun hasn’t changed much.")
        check_transfer_explanation("queue", "delay", "D arrives at minute three, so only C waits at minute two.")
        with self.assertRaisesRegex(ValueError, "same day"):
            check_transfer_explanation("seasons", "angle", "The distance to the Sun hasn’t changed.")
        check_transfer_explanation("percent", "restore", "Twenty-five percent restores the price.")
        for stage, line in (("down", "Twenty percent of eighty is twenty-five."),
                            ("base", "The first discount comes from the new lower amount.")):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                check_transfer_explanation("percent", stage, line)
        check_transfer_explanation("salary", "after", "B earns sixty thousand and C earns eighty thousand.")
        with self.assertRaisesRegex(ValueError, "twenty-five percent"):
            check_transfer_explanation("percent", "restore", "Twenty percent is not enough.")
        with self.assertRaisesRegex(ValueError, "mean goes"):
            check_transfer_explanation("salary", "before", "The mean is sixty thousand divided by three.")
        with self.assertRaisesRegex(ValueError, "current card"):
            check_transfer_explanation("study", "question", "Look at the title of the first document.")

    def test_clock_answer_follows_the_path_and_does_not_change_the_earth_clock(self):
        with self.assertRaisesRegex(ValueError, "without giving"):
            check_clock_explanation("shift", "The light path stretches to five units.")
        check_clock_explanation("shift", "The mirror is three units farther right at reflection.")
        check_clock_explanation("path", "The light path is five units.")
        with self.assertRaisesRegex(ValueError, "did not change"):
            check_clock_explanation("one-year", "The path through space stretches Earth’s clock’s numbers.")
        check_clock_explanation("one-year", "Earth measures about seven point zero nine years for that leg.")

    def test_clock_rays_end_on_the_same_named_mirror_event(self):
        emission, reflection = light_events((.39, .76), 3)
        overlays = clock("path")
        self.assertIn({"type": "segment", "from": emission, "to": reflection, "ink": "accent"}, overlays)
        self.assertIn([*reflection], [o["at"] for o in overlays if o.get("shape") == "rect"])
        self.assertAlmostEqual(math.hypot(reflection[0] - emission[0], (reflection[1] - emission[1]) * 16 / 9),
                               5 * .105)

    def test_settlement_and_repayment(self):
        a, b, c, d = [ledger_at(i) for i in range(4)]
        self.assertEqual([sum(k["reserves"] for k in row.values()) for row in (a,b,c,d)], [14_000_000] * 4)
        self.assertEqual([row["A"]["loan"] for row in (b,c,d)], [10_000_000, 10_000_000, 9_900_000])
        self.assertEqual(c["B"]["new deposit"], 10_000_000)
        self.assertIn("$100,000 in reserves", [o.get("text") for o in bank("settlement")])

    def test_citation_exhibits_different_populations(self):
        wrong = [o.get("text") for o in citation("reject")]
        right = [o.get("text") for o in citation("support")]
        self.assertIn("GPT-3.5", wrong)
        self.assertNotIn("Only 18% are fabricated.", wrong)
        self.assertIn("GPT-4", right)
        self.assertIn("Only 18% are fabricated.", right)
        packet = json.loads(CITATION_PACKET.read_text())
        self.assertFalse(evidence_for(packet)["inspected"]["mismatch"]["supports"])
        wrong = deepcopy(packet)
        wrong["passages"][1]["visible_lines"][-1] = "Only 80% are fabricated."
        with self.assertRaisesRegex(ValueError, "not in the frozen paragraph"):
            evidence_for(wrong)

    def test_transfer_queue_and_projection(self):
        self.assertEqual(queue_at(2), ("B", ["C", "D"], ["A"]))
        self.assertEqual(queue_at(2, delayed=True), ("B", ["C"], ["A"]))
        def span(lat):
            return abs(project(-40, lat+1, "mercator")[1] - project(-40, lat-1, "mercator")[1])
        self.assertGreater(span(60), 1.9 * span(0))

    def test_selection_routes_by_obligation_not_title(self):
        rule = {"obligation": "source-verification", "topic": "Why does it happen?"}
        before = skill_for(rule, "routed")
        rule["topic"] = "A new headline"
        self.assertEqual(skill_for(rule, "routed"), before)
        rule["obligation"] = "spatial"
        self.assertNotEqual(skill_for(rule, "routed"), before)

    def test_malformed_cue_cannot_advance_a_panel(self):
        brief = json.loads(Path("episodes/development/decisive.json").read_text())[0]
        sentence = "Here is the same light pulse traveling between two mirrors with an exact endpoint."
        draft = {"sections": [{"stage": stage, "text": sentence, "caption": "One pulse.", "cue": ""}
                              for stage, _ in brief["stages"]]}
        _, beats = compile_chapter(brief, draft, "probe")
        self.assertEqual(beats[1]["cue"]["phrase"], "Here is the")
        draft["sections"][1]["cue"] = "Words not spoken"
        with self.assertRaisesRegex(ValueError, "cue must bind"):
            compile_chapter(brief, draft, "probe")
