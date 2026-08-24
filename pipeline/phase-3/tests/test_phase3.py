import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from seeded_evaluation import run_seeded_evaluation  # noqa: E402


class Phase3AlertEvaluationTest(unittest.TestCase):
    def test_seeded_demand_spike_and_normal_variation(self) -> None:
        result = run_seeded_evaluation()
        self.assertEqual(result["status"], "pass")
        self.assertTrue(all(result["assertions"].values()))
        self.assertEqual(result["confusion_counts"]["true_positives"], 1)
        self.assertEqual(result["confusion_counts"]["false_positives"], 0)
        self.assertEqual(result["confusion_counts"]["false_negatives"], 0)


if __name__ == "__main__":
    unittest.main()
