import unittest

from body_progress import comparison_support, duplicated, rate_evidence
from discovery_review import locate
from derive_assertions import derive, search


class WholeQualification(unittest.TestCase):
    def test_source_support_distinguishes_return_from_input(self):
        source = "A takes in 100 kWh and returns 75 kWh. B takes in 60 kWh and returns 48 kWh."
        self.assertEqual(comparison_support("A returns more kWh than B.", source), "supports")
        self.assertEqual(comparison_support("B returns more kWh than A.", source), "contradicts")
        self.assertIsNone(comparison_support("A returns more kW than B.", source))

    def test_duplicate_text_not_static_art_is_the_defect(self):
        first = {"narration": "Here we count all the objects and then compare the visible totals together."}
        new = {"narration": "Now remove the smallest object and calculate how the average changes."}
        self.assertFalse(duplicated([{"sections": [first]}, {"sections": [new]}]))
        self.assertEqual(duplicated([{"sections": [first]}, {"sections": [first]}])[0]["chapter"], 2)

    def test_relative_efficiency_uses_exact_ratios_only_with_supported_definition(self):
        source = ("A takes in 100 kWh and returns 75 kWh. B takes in 60 kWh and returns 48 kWh. "
                  "Round-trip efficiency is returned energy divided by input energy.")
        self.assertEqual(comparison_support("B has higher round-trip efficiency than A.", source,
                                            allow_ratio=True), "supports")
        self.assertEqual(comparison_support("A has higher round-trip efficiency than B.", source,
                                            allow_ratio=True), "contradicts")
        self.assertEqual(comparison_support("B's round-trip efficiency is 80%.", source,
                                            allow_ratio=True), "supports")
        self.assertEqual(comparison_support("B's round-trip efficiency is 48%.", source,
                                            allow_ratio=True), "contradicts")

    def test_locate_only_unique_exact_heard_quote(self):
        speech = [{"word": "two", "start": 4, "end": 4.2}, {"word": "people", "start": 4.2, "end": 4.5}]
        self.assertEqual(locate("two people", speech), [4, 4.5])
        self.assertIsNone(locate("one person", speech))
        self.assertIsNone(locate("two people", speech + speech))

    def test_money_rule_derived_before_audio_does_not_flag_rewind(self):
        rule, = derive("Starting roster $20,000, $30,000 and $50,000. "
                       "When $20,000 leaves only $30,000 and $50,000 remain.",
                       "Show a payroll rewind and the remaining salaries.")
        def timed(text):
            return [{"word": " "+term, "start": i, "end": i+.9} for i, term in enumerate(text.split())]
        rewind = "Look at the original roster $20,000 $30,000 and $50,000."
        self.assertIsNone(search(timed(rewind), rule))
        self.assertIsNone(search(timed("The remaining salaries are $30,000 and $50,000."), rule))
        self.assertEqual(search(timed("The remaining salaries are $20,000 and $50,000."), rule)["start_seconds"], 0)

    def test_exact_rate_distinguishes_equal_results_from_close_values(self):
        values = rate_evidence(["Park route covers 9 km and takes 27 min. "
                                "New route covers 15 km and takes 45 min."])["distance/duration (km/min)"]
        self.assertEqual([r["exact_rate"] for r in values], ["1/3", "1/3"])
