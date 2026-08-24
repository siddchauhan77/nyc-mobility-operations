import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from seeded_validation import run_seeded_validation  # noqa: E402


class Phase2PreparationTest(unittest.TestCase):
    def test_seeded_invalid_records(self) -> None:
        result = run_seeded_validation()
        self.assertEqual(result["status"], "pass")
        self.assertTrue(all(result["assertions"].values()))


if __name__ == "__main__":
    unittest.main()
