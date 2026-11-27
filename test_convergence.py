import unittest

from opening_bindings import bind_selection, literal_rows, paired_options
from opening_assertions import observed_assertion
from opening_review import heard_numbers, measured_quantities, reconcile_judgment
from qualification_stats import lower_successes, paired


class BindingsTests(unittest.TestCase):
    def test_return_and_input_cannot_be_interchanged(self):
        rows = literal_rows(["Battery B takes in 60 kWh and returns 48 kWh. "
                             "Battery A takes in 100 kWh and returns 75 kWh."])
        self.assertEqual([(r["entity"], r["property"], r["value"]) for r in rows],
                         [("Battery B", "input", 60), ("Battery B", "return", 48),
                          ("Battery A", "input", 100), ("Battery A", "return", 75)])
        selection = {"first": 1, "second": 3, "hidden_property": "input",
                     "question": "Which battery is more efficient?", "next_line": "Compare what went in."}
        plan = bind_selection(rows, selection, {"fact-1"})
        self.assertIn("forty-eight kilowatt-hours", plan["states"][0]["narration"])
        self.assertIn("seventy-five kilowatt-hours", plan["states"][1]["narration"])
        with self.assertRaisesRegex(ValueError, "different properties"):
            bind_selection(rows, {**selection, "first": 0}, {"fact-1"})

    def test_energy_and_power_are_not_parallel(self):
        rows = literal_rows(["A returns 75 kWh. B returns 75 kW."])
        with self.assertRaisesRegex(ValueError, "different properties or units"):
            bind_selection(rows, {"first": 0, "second": 1}, set())

    def test_binding_options_keep_swapped_source_order(self):
        rows = literal_rows(["Present B first: it takes in 120 kWh and returns 84 kWh. "
                             "A takes in 60 kWh and returns 48 kWh."])
        self.assertEqual([(r["entity"], r["value"]) for r in rows], [("B",120), ("B",84), ("A",60), ("A",48)])
        self.assertIn({"first":1, "second":3, "hidden_property":"input"}, paired_options(rows))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            paired_options(rows + [{**rows[0], "value": 121}])

    def test_fixed_sample_bounds_and_empty_denominator(self):
        self.assertGreater(lower_successes(59, 59), .95)
        self.assertLess(lower_successes(58, 58), .95)
        self.assertGreater(lower_successes(299, 299), .99)
        self.assertLess(lower_successes(298, 298), .99)
        self.assertIsNone(lower_successes(0, 0))
        self.assertEqual(paired(2, 1, 1)["difference"], .25)

    def test_energy_unit_equivalence_preserves_power_distinction(self):
        self.assertEqual(list(measured_quantities("seventy-five kilowatt-hours")), [(75, "kWh")])
        self.assertEqual(list(measured_quantities("75kWh")), [(75, "kWh")])
        self.assertEqual(list(measured_quantities("75 kW")), [(75, "kW")])
        self.assertEqual(list(measured_quantities("one hundred and twenty kilowatt-hours")), [(120, "kWh")])
        self.assertEqual(heard_numbers("This one returns forty-eight."), {48})

    def test_timed_value_list_keeps_comma_split_amount(self):
        words = [{"word": part, "start": index*.2, "end": index*.2+.15}
                 for index, part in enumerate("the remaining salaries are $40 ,000 and $80 ,000.".split())]
        rule = {"kind": "listed_values", "subject": "the remaining salaries", "interval": [50, 56],
                "expected": [60000, 80000]}
        self.assertIn("[40000.0, 80000.0]", observed_assertion(words, rule, origin=51)["detail"])
        self.assertIsNone(observed_assertion(words, {**rule, "expected": [40000, 80000]}, origin=51))

    def test_conflicting_reviewer_fields_do_not_turn_into_an_approval(self):
        observed = {"status": "uncertain", "code": "ok", "start_seconds": 0,
                    "detail": "Missing focus", "repair": "Write a different opening"}
        result = reconcile_judgment(observed, 15)
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["code"], "unobservable")
        self.assertFalse(result["repair"])
        self.assertEqual(result["original_judgment"], observed)
