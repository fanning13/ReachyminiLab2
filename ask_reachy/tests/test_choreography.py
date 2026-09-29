"""Choreography stays the same shape at both study energies."""

import unittest

from ask_reachy.choreography import (
    CHOREOGRAPHY,
    ENTHUSIASTIC_ENERGY,
    RESERVED_ENERGY,
    choreography_duration_s,
    condition_label,
    scaled_choreography,
    validate_energy,
)
from ask_reachy.speech import SCRIPTED_ANSWER, load_scripted_answer


class ChoreographyTests(unittest.TestCase):
    def test_study_labels(self) -> None:
        self.assertEqual(condition_label(0.25), "Reserved")
        self.assertEqual(condition_label(0.90), "Enthusiastic")
        self.assertEqual(condition_label(0.5), "Custom")

    def test_energy_bounds(self) -> None:
        self.assertEqual(validate_energy(0.25), 0.25)
        self.assertEqual(validate_energy(0.90), 0.90)
        with self.assertRaises(ValueError):
            validate_energy(1.1)
        with self.assertRaises(ValueError):
            validate_energy(-0.01)

    def test_sequence_is_identical_except_amplitude(self) -> None:
        reserved = scaled_choreography(RESERVED_ENERGY)
        enthusiastic = scaled_choreography(ENTHUSIASTIC_ENERGY)
        self.assertEqual(len(reserved), len(CHOREOGRAPHY))
        self.assertEqual(len(enthusiastic), len(CHOREOGRAPHY))
        self.assertEqual([g.name for g in reserved], [g.name for g in enthusiastic])
        self.assertEqual(
            [g.duration_s for g in reserved],
            [g.duration_s for g in CHOREOGRAPHY],
        )
        self.assertEqual(
            [g.duration_s for g in enthusiastic],
            [g.duration_s for g in reserved],
        )
        ratio = ENTHUSIASTIC_ENERGY / RESERVED_ENERGY
        for low, high in zip(reserved, enthusiastic):
            self.assertAlmostEqual(high.pitch_deg, low.pitch_deg * ratio)
            self.assertAlmostEqual(high.roll_deg, low.roll_deg * ratio)
            self.assertAlmostEqual(high.yaw_deg, low.yaw_deg * ratio)
            self.assertAlmostEqual(
                high.right_antenna_rad, low.right_antenna_rad * ratio
            )
            self.assertAlmostEqual(high.left_antenna_rad, low.left_antenna_rad * ratio)
            self.assertAlmostEqual(high.body_yaw_rad, low.body_yaw_rad * ratio)

    def test_duration_does_not_depend_on_energy(self) -> None:
        self.assertAlmostEqual(choreography_duration_s(), 6.40)
        self.assertEqual(
            sum(g.duration_s for g in scaled_choreography(0.25)),
            sum(g.duration_s for g in scaled_choreography(0.90)),
        )

    def test_scripted_answer_matches_recording_sidecar(self) -> None:
        self.assertEqual(load_scripted_answer(), SCRIPTED_ANSWER)
        self.assertNotIn("language model", SCRIPTED_ANSWER.lower())


if __name__ == "__main__":
    unittest.main()
