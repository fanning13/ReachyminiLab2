"""Choreography stays the same shape at both study energies."""

import random
import unittest

from ask_reachy.choreography import (
    CHOREOGRAPHY,
    ENTHUSIASTIC_ANTENNA_RAD,
    ENTHUSIASTIC_BEAT_S,
    ENTHUSIASTIC_CHOREOGRAPHY,
    ENTHUSIASTIC_ENERGY,
    ENTHUSIASTIC_PITCH_DEG,
    RESERVED_ENERGY,
    SHY_ANTENNAS_RAD,
    SHY_CHOREOGRAPHY,
    choreography_duration_s,
    condition_label,
    scaled_choreography,
    validate_energy,
)
from ask_reachy.speech import (
    CONTINUE_QUESTION,
    CURIOUS,
    END_STORY,
    INTRO,
    PROMPT_A,
    PROMPT_B,
    SHY,
    STORY_FOLLOWUPS,
    STUDY_CLOSING,
    WHATS_NEXT,
    line_duration_s,
    load_all_lines,
    load_line,
    plan_session,
)
from ask_reachy.transcribe import classify_yes_no


class ChoreographyTests(unittest.TestCase):
    def test_study_labels(self) -> None:
        self.assertEqual(condition_label(0.25), "Shy")
        self.assertEqual(condition_label(0.90), "Curious")
        self.assertEqual(condition_label(0.5), "Custom")

    def test_energy_bounds(self) -> None:
        self.assertEqual(validate_energy(0.25), 0.25)
        self.assertEqual(validate_energy(0.90), 0.90)
        with self.assertRaises(ValueError):
            validate_energy(1.1)
        with self.assertRaises(ValueError):
            validate_energy(-0.01)

    def test_custom_energy_scales_the_open_sequence(self) -> None:
        scaled = scaled_choreography(0.50)
        self.assertEqual([g.name for g in scaled], [g.name for g in CHOREOGRAPHY])
        self.assertEqual(
            [g.duration_s for g in scaled],
            [g.duration_s for g in CHOREOGRAPHY],
        )
        for gesture, full in zip(scaled, CHOREOGRAPHY):
            self.assertAlmostEqual(gesture.pitch_deg, full.pitch_deg * 0.50)

    def test_enthusiastic_bobs_and_flicks(self) -> None:
        enthusiastic = scaled_choreography(ENTHUSIASTIC_ENERGY)
        self.assertEqual(enthusiastic, ENTHUSIASTIC_CHOREOGRAPHY)
        self.assertGreater(len(enthusiastic), len(SHY_CHOREOGRAPHY))
        for index, gesture in enumerate(enthusiastic):
            self.assertEqual(gesture.duration_s, ENTHUSIASTIC_BEAT_S)
            self.assertLess(gesture.duration_s, min(g.duration_s for g in SHY_CHOREOGRAPHY))
            expected_pitch = (
                -ENTHUSIASTIC_PITCH_DEG if index % 2 == 0 else ENTHUSIASTIC_PITCH_DEG
            )
            self.assertEqual(gesture.pitch_deg, expected_pitch)
            self.assertEqual(gesture.z_m, 0.0)
            self.assertEqual(abs(gesture.right_antenna_rad), ENTHUSIASTIC_ANTENNA_RAD)
            self.assertEqual(gesture.left_antenna_rad, -gesture.right_antenna_rad)
            if index:
                self.assertNotEqual(
                    gesture.right_antenna_rad,
                    enthusiastic[index - 1].right_antenna_rad,
                )

    def test_reserved_is_the_shy_hiding_pose(self) -> None:
        reserved = scaled_choreography(RESERVED_ENERGY)
        self.assertEqual(reserved, SHY_CHOREOGRAPHY)
        for gesture in reserved:
            self.assertEqual(
                (gesture.right_antenna_rad, gesture.left_antenna_rad),
                SHY_ANTENNAS_RAD,
            )
            self.assertGreaterEqual(gesture.pitch_deg, 30.0)
            self.assertLess(gesture.pitch_deg, 40.0)
            self.assertLess(gesture.z_m, -0.03)

    def test_duration_does_not_depend_on_energy(self) -> None:
        self.assertAlmostEqual(choreography_duration_s(), 6.40)
        self.assertAlmostEqual(
            sum(g.duration_s for g in scaled_choreography(0.25)),
            6.40,
        )
        self.assertAlmostEqual(
            sum(g.duration_s for g in scaled_choreography(0.90)),
            13 * ENTHUSIASTIC_BEAT_S,
        )

    def test_story_lines_are_fixed(self) -> None:
        self.assertEqual(
            [line.text for line in STORY_FOLLOWUPS],
            [
                "That's interesting. What's next?",
                "That's interesting. What's next?",
                "Interesting story. Would you like to continue expanding it?",
            ],
        )
        self.assertEqual(STORY_FOLLOWUPS[0], WHATS_NEXT)
        self.assertEqual(STORY_FOLLOWUPS[2], CONTINUE_QUESTION)
        self.assertIn("Story 1", END_STORY[1].text)
        self.assertIn("Story 2", END_STORY[2].text)
        self.assertTrue(INTRO.text.startswith("Hi there, I'm Reachy Mini"))
        self.assertTrue(STUDY_CLOSING.text.startswith("That conclude our study."))
        self.assertIn("fallen leaves", PROMPT_A.line.text)
        self.assertIn("familiar street", PROMPT_B.line.text)

    def test_session_plan_uses_both_prompts_and_both_styles(self) -> None:
        plan = plan_session(random.Random(7))
        self.assertEqual(plan_session(random.Random(7)), plan)
        self.assertEqual({slot.prompt.key for slot in plan}, {"A", "B"})
        self.assertEqual(
            {slot.characteristic.name for slot in plan},
            {SHY.name, CURIOUS.name},
        )
        self.assertEqual(SHY.motion_energy, 0.25)
        self.assertEqual(CURIOUS.motion_energy, 0.90)

    def test_yes_no_classification(self) -> None:
        self.assertEqual(classify_yes_no("Yes, I would."), "Yes")
        self.assertEqual(classify_yes_no("yeah sure"), "Yes")
        self.assertEqual(classify_yes_no("No thanks."), "No")
        self.assertEqual(classify_yes_no("nope"), "No")
        self.assertEqual(classify_yes_no("yes and no"), "Unclear")
        self.assertEqual(classify_yes_no(""), "Unclear")
        self.assertEqual(classify_yes_no("maybe later"), "Unclear")

    def test_scripted_lines_match_recordings(self) -> None:
        load_all_lines()
        lines = (
            INTRO,
            PROMPT_A.line,
            PROMPT_B.line,
            WHATS_NEXT,
            CONTINUE_QUESTION,
            END_STORY[1],
            END_STORY[2],
            STUDY_CLOSING,
        )
        for line in lines:
            self.assertEqual(load_line(line), line.text)
            self.assertGreater(line_duration_s(line), 0.3)
            self.assertLess(line_duration_s(line), 20.0)


if __name__ == "__main__":
    unittest.main()
