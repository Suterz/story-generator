import math
import unittest

from episode_graphics import bank, citation, clock, ledger_at, light_events


class EvidenceTests(unittest.TestCase):
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
