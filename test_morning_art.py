import unittest

from morning_art import DESIGNS, stage_art
from storygen import validate


class MorningArtTests(unittest.TestCase):
    def test_all_spoken_designs_use_the_existing_schema_and_exact_cues(self):
        self.assertEqual(set(DESIGNS), {f"{i:02}" for i in range(1, 21)} - {"01", "02", "19"})
        for slot, make in DESIGNS.items():
            with self.subTest(slot=slot):
                story = make()
                validate(story)
                self.assertTrue(story["beats"][0]["panel"]["paper_scene"])
                for beat in story["beats"]:
                    self.assertLessEqual(len(beat["panel"]["overlays"]), 40)
                    self.assertTrue(beat["panel"]["overlays"])

    def test_stage_keeps_its_curtain_and_changes_light(self):
        dark, light = stage_art(), stage_art(True)
        self.assertNotEqual(dark, light)
        self.assertEqual(dark[:7], light[:7])
