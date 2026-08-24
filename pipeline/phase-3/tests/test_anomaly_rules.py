import sys
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from run_phase3 import metric_is_alert, payment_total_variation, robust_z  # noqa: E402


class DeterministicAnomalyTests(unittest.TestCase):
    def test_seeded_demand_spike_is_flagged(self):
        baseline = [96, 100, 104, 98, 102]
        median = 100.0
        mad = 2.0
        self.assertGreater(robust_z(180, median, mad), 3.5)
        self.assertTrue(metric_is_alert(180, median, mad, z_threshold=3.5, relative_threshold=0.25))

    def test_seeded_normal_variation_is_not_flagged(self):
        self.assertFalse(metric_is_alert(104, 100, 2, z_threshold=3.5, relative_threshold=0.25))

    def test_zero_mad_is_not_scored(self):
        self.assertIsNone(robust_z(150, 100, 0))
        self.assertFalse(metric_is_alert(150, 100, 0, z_threshold=3.5, relative_threshold=0.25))

    def test_relative_gate_blocks_small_operational_shift(self):
        self.assertFalse(metric_is_alert(108, 100, 1, z_threshold=3.5, relative_threshold=0.25))

    def test_seeded_payment_distribution_spike_is_flagged(self):
        distance = payment_total_variation([0.45, 0.55], [0.75, 0.25])
        self.assertAlmostEqual(distance, 0.30)
        self.assertGreaterEqual(distance, 0.20)

    def test_seeded_payment_normal_variation_is_not_flagged(self):
        distance = payment_total_variation([0.72, 0.28], [0.75, 0.25])
        self.assertAlmostEqual(distance, 0.03)
        self.assertLess(distance, 0.20)

    def test_payment_vectors_must_align(self):
        with self.assertRaises(ValueError):
            payment_total_variation([1.0], [0.5, 0.5])


if __name__ == "__main__":
    unittest.main()
